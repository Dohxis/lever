from rpython.config.translationoption import get_combined_translation_config
from rpython.rlib.rtimer import read_timestamp
from rpython.rlib.objectmodel import we_are_translated
from rpython.rlib.rstacklet import StackletThread
from space import *
import base

class ProcessState:
    stacklet = None
    current = None
    
    def init(self, config):
        self.stacklet = StackletThread(config)
        self.current = Greenlet(
            self.stacklet.get_null_handle(),
            True)
process = ProcessState()

class Greenlet(Object):
    def __init__(self, handle, initialized, argv=None):
        self.handle = handle
        self.initialized = initialized
        self.argv = argv
        self.parent = process.current
        self.callee = None

    def switch(self, argv):
        if not self.initialized:
            self.argv += argv
            self.initialized = True
            self.callee = process.current
            process.current = self
            self.handle = process.stacklet.new(greenlet_init)
            callee = process.stacklet.switch(self.handle)
            process.current.callee.handle = callee
        else:
            if process.stacklet.is_empty_handle(self.handle):
                raise Error("dead greenlet")
            self.argv = argv
            self.callee = process.current
            process.current = self
            callee = process.stacklet.switch(self.handle)
            process.current.callee.handle = callee
        if len(process.current.argv) == 0:
            retval = null
        else:
            retval = process.current.argv[0]
        process.current.argv = None
        return retval

    def getattr(self, name):
        if name == 'switch':
            return GreenletSwitch(self)
        if name == 'parent':
            return self.parent or null
        return Object.getattr(self, name)

    def repr(self):
        return "<greenlet " + str(self.handle) + ">"

class GreenletSwitch(Object):
    def __init__(self, greenlet):
        self.greenlet = greenlet

    def call(self, argv):
        return self.greenlet.switch(argv)

    def repr(self):
        return self.greenlet.repr() + ".switch"

def greenlet_init(head, arg):
    # fill greenlet's handle.
    callee = process.stacklet.switch(head)
    process.current.callee.handle = callee
    current = process.current

    func = current.argv.pop(0)
    retval = func.call(current.argv)

    parent = process.current.parent
    while process.stacklet.is_empty_handle(parent.handle):
        parent = parent.parent
    parent.argv = [retval]
    parent.callee = process.current
    process.current = parent
    return parent.handle

@base.builtin
def getcurrent(argv):
    return process.current

@base.builtin
def greenlet(argv):
    return Greenlet(process.current.handle, False, argv)
