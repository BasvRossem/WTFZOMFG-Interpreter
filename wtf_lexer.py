"""A WTFZOMFG Lexer"""
from copy import deepcopy
from itertools import accumulate
import time
from typing import List, Tuple, Union

from wtf_errors import UnknownCharacterError, WtfError
from wtf_objects import LexerStates, LexerVars, Token

TOKENS_COMMAND = {
    # Control
    '(': 'LOOP_START',
    ')': 'LOOP_END',
    '{': 'IF_START',
    '}': 'IF_END',

    # Cell/Pointer Manipulation
    '+': 'CELL_INCREASE',
    '-': 'CELL_DECREASE',
    '|': 'CELL_FLIP',

    '&': 'COPY_VALUE_RIGHT',

    '<': 'POINTER_MOVE_LEFT',
    '>': 'POINTER_MOVE_RIGHT',

    # Arithmetic
    'a': 'CELL_ADD_RIGHT',
    's': 'CELL_SUBTRACT_RIGHT',
    'm': 'CELL_MULTIPLY_RIGHT',
    'd': 'CELL_DEVIDE_RIGHT',

    # Input/Output
    '^': 'SCAN_ASCII',
    '/': 'SCAN_DECIMAL',
    'v': 'PRINT_CELL_ASCII',
    '\\': 'PRINT_CELL_DECIMAL',

    # Debug
    'w': "PRINT_PROGRAM_STATE"}

TOKENS_COMMAND_VALUE = {
    # Control
    ':': 'LABEL_GOTO',
    ';': 'LABEL_DECLARE',
    '?': 'LABEL_GOTO_NONZERO',
    '!': 'LABEL_GOTO_ZERO',

    # Cell/Pointer Manipulation
    '=': 'CELL_SET',
    '~': 'CELL_INCREASE_WITH',

    '%': 'COPY_VALUE_TO',

    '_': 'POINTER_MOVE_TO',
    '*': 'POINTER_MOVE_RELATIVE',

    '@': 'CELL_SUBTRACT_ASCII',

    # Input/Output
    '.': 'PRINT_CHARACTER',

    '\'': 'PRINT_UNTIL',
    '\"': 'PRINT_STOP',

    # Commenting
    '#': 'COMMENT',
    '[': 'COMMENT_START',
    ']': 'COMMENT_END'}

LEXER_COMMANDS = [
    'ADD_TO_PREVIOUS']


def switch_lexer_state(lexer_state: LexerStates, command: str) -> LexerStates:
    """
    This function returns a state depending on the command
    """
    state = deepcopy(lexer_state)
    if command == 'COMMENT':
        state = LexerStates.GO_UNTIL_NEWLINE
    elif command == 'PRINT_UNTIL':
        state = LexerStates.GO_UNTIL_END_PRINT
    elif command == 'COMMENT_START':
        state = LexerStates.GO_UNTIL_END_COMMENT
    return state


def find_token(lexer_vars: LexerVars, word: str) -> Tuple[LexerVars, Token]:
    """
    A function that creates a token using an word
    """
    lxr_vrs = deepcopy(lexer_vars)
    token = Token(None, None)

    # The lexer will try to make a new token
    if lxr_vrs.state == LexerStates.DEFAULT:
        # The word is a valid single character command
        # print(word)
        if word in TOKENS_COMMAND and len(word) == 1:
            token.command = TOKENS_COMMAND[word]
        # The word is a valid single character command that reqiures a value
        elif word[0] in TOKENS_COMMAND_VALUE:
            token.command = TOKENS_COMMAND_VALUE[word[0]]
            token.value = word[1:]
            lxr_vrs.state = switch_lexer_state(lxr_vrs.state, token.command)
            # If the command is a multi character print
            if token.command == 'PRINT_UNTIL' and word[-1] == '"':
                token.value = word[1:-1]
                lxr_vrs.state = LexerStates.DEFAULT
            # If the command is a multi character comment
            if token.command == 'COMMENT_START' and word[-1] == ']':
                token.value = word[1:-1]
                lxr_vrs.state = LexerStates.DEFAULT
        # The Token is unknown in the list
        elif word != "\n":
            line_nr = lxr_vrs.line_nr + 1
            word_nr = lxr_vrs.word_nr + 1
            error = UnknownCharacterError(word[0], word, line_nr, word_nr)
            lxr_vrs.errors.append(error)
    # The lexer will need to add these tokens to the last, so mark them if needed
    elif lxr_vrs.state != LexerStates.DEFAULT:
        token.command = 'ADD_TO_PREVIOUS'
        combinations = [
            lxr_vrs.state == LexerStates.GO_UNTIL_NEWLINE and word[-1] == '\n',
            lxr_vrs.state == LexerStates.GO_UNTIL_END_PRINT and word[-1] == '\"',
            lxr_vrs.state == LexerStates.GO_UNTIL_END_COMMENT and word[-1] == ']'
        ]
        if any(combinations):
            token.value = word[:-1]
            lxr_vrs.state = LexerStates.DEFAULT
        else:
            token.value = word

    # Remove empty add to previous that have nothing to do with the string
    if token.value == "\n":
        token.command = None
        token.value = None
    # print(token)
    return lxr_vrs, token

def combine_tokens_core(token, next_token) -> List[Token]:
    """
    Extends the next token value when needed.
    """
    deepcopy(next_token)
    if token.command == 'ADD_TO_PREVIOUS':
        next_token.value += ' ' + token.value

    return next_token

def combine_tokens(token_list: List[Token]) -> List[Token]:
    """
    Combines tokens with the next token in the sequence if needed.
    """
    tokens = deepcopy(token_list)
    tokens = list(accumulate(tokens, combine_tokens_core))
    tokens = list(filter(lambda token: token.command != 'ADD_TO_PREVIOUS', tokens))
    return tokens


def remove_comments(token_list: List[Token]) -> List[Token]:
    """
    Removes comment tokens
    """
    return list(filter(lambda t: not (t.command == 'COMMENT' or t.command == 'COMMENT_START'), token_list))


def cleanup_tokens(token_list: List[Token]) -> List[Token]:
    """
    A function that cleans up the given tokens.

    This is done in three steps:
    1. Filtering out all None tokens
    2. Combining tokens when necessary
    3. Filtering out all None tokens once more

    Returns a list of tokens
    """
    tokens = deepcopy(token_list)

    tokens = list(filter(lambda token: token.command, tokens))
    tokens.reverse()
    tokens = combine_tokens(tokens)
    tokens.reverse()
    tokens = remove_comments(tokens)
    tokens = list(filter(lambda token: token.command, tokens))

    return tokens


def process_line(lexer_vars: LexerVars) -> Tuple[LexerVars, List[Token]]:
    """
    Returns a list of tokens which depend on the previously generated tokens
    """
    lxr_vrs = deepcopy(lexer_vars)

    if not lxr_vrs.word_nr < len(lxr_vrs.source[lxr_vrs.line_nr]):
        return lxr_vrs, lxr_vrs.tokens

    current_word = lxr_vrs.source[lxr_vrs.line_nr][lxr_vrs.word_nr]

    lxr_vrs, token = find_token(lxr_vrs, current_word)
    lxr_vrs.tokens.append(token)
    lxr_vrs.word_nr += 1

    return process_line(lxr_vrs)


def process_lines(lexer_vars: LexerVars, tokens: List[Token]) -> Tuple[LexerVars, List[Token]]:
    """
    A function that recursively goes through every list in the source_list of a LexerVars
    object and generates tokens for that list using the process_line function
    """
    lexer_variables = deepcopy(lexer_vars)
    token_list = deepcopy(tokens)

    if not lexer_variables.line_nr < len(lexer_variables.source):
        return lexer_variables, token_list

    line_tokens = []
    lexer_variables, line_tokens = process_line(lexer_variables)

    token_list.extend(line_tokens)

    lexer_variables.word_nr = 0
    lexer_variables.line_nr += 1
    lexer_variables.tokens = []

    return process_lines(lexer_variables, token_list)


def lexer(source: str) -> Union[List[Token], List[WtfError]]:
    """
    A function that converts a string of characters into tokens
    Returns a list of tokens
    """
    source_list = [(line.strip("\n")).split() + ['\n'] for line in source]

    lexer_vars = LexerVars([], LexerStates.DEFAULT, source_list, 0, 0, [])
    lexer_vars, tokens = process_lines(lexer_vars, [])

    return cleanup_tokens(tokens), lexer_vars.errors
