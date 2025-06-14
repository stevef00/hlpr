#!/usr/bin/env python3


class Tool:
    def __init__(self, function, tool_definition={}):
        self.function = function
        self.definition = tool_definition

        self.definition.setdefault("type", "function")
        self.definition.setdefault("name", self.function.__name__)
        self.definition.setdefault("strict", True)
        self.definition.setdefault("parameters", {})

    def __str__(self):
        return self.function.__name__

    def call(self):
        return self.function()

    def function_name(self):
        return self.function.__name__
