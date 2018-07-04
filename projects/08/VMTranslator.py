import sys
import os
import re
import glob

class VMCommand():
    """
    provides simpler interface and encapsulation for inspecting current command
    """
    COMMENT_SYMBOL = '//'
    NEWLINE_SYMBOL = '\n'
    EMPTY_SYMBOL = ''

    def __init__(self, text):
        self.raw_text = text
        self.text = text.split(self.COMMENT_SYMBOL)[0].strip()
        self.parts = self.text.split(' ')

    def label(self):
        if not self.is_branching_command():
            return

        return self.parts[1]

    def function_name(self):
        if not self.is_function_declaration_command() and not self.is_call_command():
            return

        return self.parts[1]

    def arguments(self):
        if not self.is_call_command():
            return

        return self.parts[2]

    def locals(self):
        if not self.is_function_declaration_command():
            return

        return self.parts[2]

    def is_function_command(self):
        return self.is_function_declaration_command() or self.is_call_command() or self.is_return_command()


    def is_function_declaration_command(self):
        return self.operation() == 'function'

    def is_call_command(self):
        return self.operation() == 'call'

    def is_return_command(self):
        return self.operation() == 'return'

    def is_branching_command(self):
        return self.is_goto_command() or self.is_label_command() or self.is_ifgoto_command()

    def is_goto_command(self):
        return self.operation() == 'goto'

    def is_ifgoto_command(self):
        return self.operation() == 'if-goto'

    def is_label_command(self):
        return self.operation() == 'label'

    def is_pushpop_command(self):
        return self.operation() == 'push' or self.operation() == 'pop'

    def is_comment(self):
        return self.raw_text[0:2] == self.COMMENT_SYMBOL

    def is_whitespace(self):
        return self.raw_text == self.NEWLINE_SYMBOL

    def is_empty(self):
        return self.raw_text == self.EMPTY_SYMBOL

    def segment(self):
        # only for memory access commands
        if len(self.parts) != 3:
            return

        return self.parts[1]

    def index(self):
        # only for memory access commands
        if len(self.parts) != 3:
            return

        return self.parts[2]

    def operation(self):
        return self.parts[0]

class VMParser():
    """
    Encapsulates access to the input code in the file
    Reads VM commands, parses them and provides a convenient access to their components
    Ignores Whitespace and Comments
    """
    def __init__(self, input_file):
        self.input_file = open(input_file, 'r')
        self.has_more_commands = True
        self.current_command = None
        self.next_command = None

    def has_valid_current_command(self):
        return not self.current_command.is_whitespace() and not self.current_command.is_comment()

    def advance(self):
        self._update_current_command()
        self._update_next_command()
        self._update_has_more_commands()

    def _update_has_more_commands(self):
        if self.next_command.is_empty():
            self.has_more_commands = False

    def _update_next_command(self):
        text = self.input_file.readline()
        self.next_command = VMCommand(text)

    def _update_current_command(self):
        # initialization
        if self.current_command == None:
            text = self.input_file.readline()
            self.current_command = VMCommand(text)
        else:
            self.current_command = self.next_command

class VMWriter():
    """
    simply wrapper for interacting with output file
    """
    def __init__(self, input_file):
        self.output_file = open(self._output_file_name_from(input_file), 'w')

    def write(self, command):
        self.output_file.write(command)

    def close_file(self):
        self.output_file.close()

    def _output_file_name_from(self, input_file):
        return input_file.split('.')[0] + '.asm'


class VMArithmeticTranslator():
    OPERATION_INSTRUCTIONS = {
        'add': 'M=M+D',
        'sub': 'M=M-D',
        'neg': 'M=-M',
        'or' : 'M=M|D',
        'not': 'M=!M',
        'and': 'M=M&D'
    }

    COMP_COMMANDS = {
        'eq': { 'jump_directive': 'JNE'},
        'lt': { 'jump_directive': 'JGE'},
        'gt': { 'jump_directive': 'JLE'}
    }

    def __init__(self):
        self.comp_counters = {
            'eq' : { 'count': 0 },
            'lt' : { 'count': 0 },
            'gt' : { 'count': 0 }
        }

    def translate(self, command):
        if command.text in self.COMP_COMMANDS:
            return self.comp_translation(command.text)
        else:
            return self.arithmetic_translation(command.text)

    def arithmetic_translation(self, command_text):
        # binary operation
        if command_text in [ 'add', 'sub', 'and', 'or' ]:
            return [
                *self.pop_top_number_off_stack_instructions(),
                # put in temp D for operation
                'D=M',
                *self.pop_top_number_off_stack_instructions(),
                self.OPERATION_INSTRUCTIONS[command_text],
                *self.increment_stack_pointer_instructions()
            ]
        else: # unary operation
            return [
                *self.pop_top_number_off_stack_instructions(),
                self.OPERATION_INSTRUCTIONS[command_text],
                *self.increment_stack_pointer_instructions()
            ]

    def comp_translation(self, command_text):
        counter = self.comp_counters[command_text]
        counter['count'] += 1
        label_identifier = '{}{}'.format(command_text.upper(), counter['count'])
        jump_directive = self.COMP_COMMANDS[command_text]['jump_directive']

        return [
            *self.pop_top_number_off_stack_instructions(),
            # set D to top of stack
            'D=M',
            *self.pop_top_number_off_stack_instructions(),
            # set D to x-y
            'D=M-D',
            # load not true label
            '@NOT_{}'.format(label_identifier),
            # jump to not true section on directive
            'D;{}'.format(jump_directive),
            # load stack pointer
            '@SP',
            # set A to top of stack address
            'A=M',
            # set it to -1 for true
            'M=-1',
            # load inc stack pointer
            '@INC_STACK_POINTER_{}'.format(label_identifier),
            # jump uncoditionally
            '0;JMP',
            # not true section
            '(NOT_{})'.format(label_identifier),
            # load stack pointer
            '@SP',
            # set A to to top of stack address
            'A=M',
            # set to 0 for false
            'M=0',
            # define inc stack pointer label
            '(INC_STACK_POINTER_{})'.format(label_identifier),
            *self.increment_stack_pointer_instructions()
        ]

    def pop_top_number_off_stack_instructions(self):
        return [
            # load stack pointer
            '@SP',
            # decrement stack pointer and set address
            'AM=M-1'
        ]

    def increment_stack_pointer_instructions(self):
        return [
            # load stack pointer
            '@SP',
            # increment stack pointer
            'M=M+1'
        ]


class VMPushPopTranslator():
    VIRTUAL_MEMORY_SEGMENTS = {
        'local'    : { 'base_address_pointer': '1' },
        'argument' : { 'base_address_pointer': '2' },
        'this'     : { 'base_address_pointer': '3' },
        'that'     : { 'base_address_pointer': '4' }
    }

    POINTER_SEGMENT_BASE_ADDRESS = '3'

    HOST_SEGMENTS = {
        'temp'  : { 'base_address': '5' },
        'static': { 'base_address': '16'}
    }

    def translate(self, command):
        if command.operation() == 'push':
            # Push the value of segment[index] onto the stack

            return [
                *self.load_desired_value_into_D_instructions_for(segment=command.segment(), index=command.index()),
                *self.place_value_in_D_on_top_of_stack_instructions(),
                *self.increment_stack_pointer_instructions()
            ]
        else: # command operation is pull
            # Pop the top-most value off the stack store in segment[index]

            return [
                *self.store_top_of_stack_in_D_instructions(),
                *self.store_top_of_stack_first_temp_register_instructions(),
                *self.load_base_address_instructions_for(segment=command.segment()),
                *self.add_index_to_base_address_in_D_instructions(index=command.index()),
                *self.store_target_address_in_second_temp_register_instructions(),
                *self.set_target_address_to_value_instructions()
            ]


    def load_desired_value_into_D_instructions_for(self, segment, index):
        if segment == 'constant':
            return [
                *self.load_value_in_D_instructions(value=index)
            ]
        else:
            return [
                *self.load_base_address_instructions_for(segment=segment),
                *self.add_index_to_base_address_in_D_instructions(index=index),
                *self.load_value_at_memory_address_in_D_instructions()
            ]

    def load_base_address_instructions_for(self, segment):
        if segment in self.VIRTUAL_MEMORY_SEGMENTS:
            pointer_to_segment_base_address = self.VIRTUAL_MEMORY_SEGMENTS[segment]['base_address_pointer']
            return self.load_referenced_value_in_D_instructions(address=pointer_to_segment_base_address)
        elif segment in self.HOST_SEGMENTS:
            host_segment_base_address = self.HOST_SEGMENTS[segment]['base_address']
            return self.load_value_in_D_instructions(value=host_segment_base_address)
        elif segment == 'pointer':
            return self.load_value_in_D_instructions(value=self.POINTER_SEGMENT_BASE_ADDRESS)


    def place_value_in_D_on_top_of_stack_instructions(self):
        return [
            # load stack pointer
            '@SP',
            # Get current address
            'A=M',
            # Store constant in address
            'M=D'
        ]

    def increment_stack_pointer_instructions(self):
        return [
            # load stack pointer
            '@SP',
            # increment stack pointer
            'M=M+1'
        ]

    def load_value_in_D_instructions(self, value):
        return [
            # load value
            '@' + value,
            # store value in D
            'D=A'
        ]

    def load_referenced_value_in_D_instructions(self, address):
        return [
            # load address
            '@' + address,
            # store address value
            'D=M'
        ]

    def add_index_to_base_address_in_D_instructions(self, index):
        return [
            '@' + index,
            'D=D+A'
        ]
    def load_value_at_memory_address_in_D_instructions(self):
        return [
            # set A to address stored in D
            'A=D',
            # now put value at new address in D
            'D=M'
        ]

    def set_address_to_top_of_stack_instructions(self, address):
        return [
            # load segment address
            '@' + address,
            # set segment equal to top of stack
            'M=D'
        ]

    def set_target_address_to_value_instructions(self):
        return [
            # load top of stack value
            '@R5',
            # store in D
            'D=M',
            # load segment + index address
            '@R6',
            # set as current address register
            'A=M',
            # set segment[index] to stack top
            'M=D'
        ]

    def store_target_address_in_second_temp_register_instructions(self):
        return [
            # load temp
            '@R6',
            # store segment + index address
            'M=D'
        ]

    # (when top of stack already in D)
    def store_top_of_stack_first_temp_register_instructions(self):
        return [
            # load temp register
            '@R5',
            # store top of stack in temp register
            'M=D'
        ]

    def store_top_of_stack_in_D_instructions(self):
        return [
            # load stack pointer
            '@SP',
            # decrement pointer to top of stack
            'AM=M-1',
            # store value in D
            'D=M'
        ]

class VMBranchingTranslator():
    def translate(self, command):
        if command.is_label_command():
            # insert label into assembly
            return [
                '({})'.format(command.label())
            ]
        elif command.is_goto_command():
            # unconditionally jump to label
            return [
                '@' + command.label(),
                '0;JMP'
            ]
        elif command.is_ifgoto_command():
            # jump if the topmost item on the stack is not equal to zero
            return [
                # pop top most item off stack
                '@SP',
                'AM=M-1',
                'D=M',
                # jump is not 0
                '@' + command.label(),
                'D;JNE'
            ]

class VMFunctionTranslator():
    def __init__(self):
        self.function_count = 0
        self.call_count = 0

    def translate(self, command):
        if command.is_function_declaration_command():
            self.function_count += 1

            return [
                # establish function label
                '({})'.format(command.function_name()),
                # push onto the stack 0 command.locals() times
                # initialize loop times
                '@' + command.locals(),
                # store in D
                'D=A',
                # store in temp?
                # establish loop label
                '(LOOP.ADD_LOCALS.{})'.format(self.function_count),
                # push 0 onto stack D times
                # load stack pointer
                '@SP',
                # get pointer address
                'A=M',
                # set to 0
                'M=0',
                # increment stack pointer
                '@SP',
                'M=M+1',
                # decrement D
                'D=D-1',
                # load loop
                '@LOOP.ADD_LOCALS.{}'.format(self.function_count),
                # jump back if not 0
                'D;JNE'
            ]
        elif command.is_call_command():
            self.call_count += 1

            return [
                "call"
            ]
        elif command.is_return_command():
            return [
                # FRAME=LCL // FRAME is a temporary variable
                '@LCL',
                'D=M', # Frame
                # load temp register
                '@R5',
                # store Frame in temp register
                'M=D',
                # RET=*(FRAME-5) // save return address in a temp. var
                # load value to subtract
                '@5',
                # store value in D
                'D=A',
                # load frame from temp
                '@R5',
                # get address value into A
                'A=M-D',
                # dereference to get value at mem address
                'D=M',
                # load into temp reg
                '@R6',
                'M=D',
                # *ARG=pop() // reposition return value for caller
                # pop of stack off into D
                '@SP',
                'AM=M-1',
                'D=M',
                # set top of arg stack to return value for caller
                '@ARG',
                'A=M',
                'M=D',
                #SP=ARG+1 // restore SP for caller
                '@ARG',
                'D=M+1',
                '@SP',
                'M=D',
                #THAT=*(FRAME-1) // restore THAT of calling function
                # load value to subtract
                '@1',
                # place in D
                'D=A',
                # load frame
                '@R5',
                # get address value into A
                'A=M-D',
                # dereference to get value at mem address
                'D=M',
                # load THAT
                '@THAT',
                # set value at THAT to D
                'M=D',
                #THIS=*(FRAME-2) // restore THIS of calling function
                # load value to subtract
                '@2',
                # place in D
                'D=A',
                # load frame
                '@R5',
                # get address value into A
                'A=M-D',
                # dereference to get value at mem address
                'D=M',
                # load THIS
                '@THIS',
                # set value at THAT to D
                'M=D',
                #ARG=*(FRAME-3) // restore ARG of calling function
                # load value to subtract
                '@3',
                # place in D
                'D=A',
                # load frame
                '@R5',
                # get address value into A
                'A=M-D',
                # dereference to get value at mem address
                'D=M',
                # load ARG
                '@ARG',
                # set value at THAT to D
                'M=D',
                #LCL=*(FRAME-4) // Restore LCL of calling function
                # load value to subtract
                '@4',
                # place in D
                'D=A',
                # load frame
                '@R5',
                # get address value into A
                'A=M-D',
                # dereference to get value at mem address
                'D=M',
                # load LCL
                '@LCL',
                # set value at THAT to D
                'M=D',
                #goto RET // GOTO the return-address
                # load RET
                '@R6',
                'A=M',
                # go to RET
                '0;JMP'
            ]




if __name__ == "__main__" and len(sys.argv) == 2:
    input = sys.argv[1]

    if os.path.isfile(input):
        vm_files = [input]
    elif os.path.isdir(input):
        vm_path = os.path.join(input, "*.vm")
        vm_files = glob.glob(vm_path)

    for vm_file in vm_files:
        parser = VMParser(vm_file)
        writer = VMWriter(vm_file)

        # maybe these go inside the translator and wrap up to 1 translate method
        arithmetic_translator = VMArithmeticTranslator()
        push_pop_translator = VMPushPopTranslator()
        branching_translator = VMBranchingTranslator()
        function_translator = VMFunctionTranslator()

        while parser.has_more_commands:
            parser.advance()

            if parser.has_valid_current_command():
                if parser.current_command.is_pushpop_command():
                    translation = push_pop_translator.translate(parser.current_command)
                elif parser.current_command.is_branching_command():
                    translation = branching_translator.translate(parser.current_command)
                elif parser.current_command.is_function_command():
                    translation = function_translator.translate(parser.current_command)
                else: # math / logical operation
                    translation = arithmetic_translator.translate(parser.current_command)

                for line in translation:
                    writer.write(line + '\n')

    writer.close_file()
