# @author _raw_data_ @ https://github.com/raw-data
# @category N/A
# @keybinding
# @menupath
# @toolbar

"""
Apply some pseudo-code changes, that recalls IDA display "style" and 
some custom ones
    - Rename all `local_xxxx` variables to `var_xxxx`
    - Rename all `FUN_xxxx` functions to `sub_xxxx`
    - Rename all `_DAT_xxxx` or `DAT_xxxx` globals to `glob_`
"""

__version__ = "v0.0.3"

from ghidra.program.model.symbol import SourceType
from ghidra.program.model.symbol import SymbolType


def globals_rename():
    # type (None) -> None
    """Rename global variables with prefix
    `DAT_` or `_DAT_` to `glob_`
    """

    glob_types = {"DAT_": "", "_DAT_": ""}

    for s in currentProgram.getSymbolTable().getAllSymbols(True):
        symbol_name = s.getName()

        for prefix, var_type in glob_types.items():
            if symbol_name.startswith(prefix):
                _new_symbol_name = var_type + "glob_" + symbol_name[len(prefix) :]
                s.setName(
                    _new_symbol_name,
                    SourceType.USER_DEFINED,
                )
                print("[i] Renamed %s to %s" % (symbol_name, _new_symbol_name))
                break

        if s.getSymbolType() == SymbolType.LABEL:
            if symbol_name.startswith("LAB_"):
                hexAddress = symbol_name[4:].upper()
                _new_symbol_name = "loc_" + hexAddress

                s.setName(_new_symbol_name, SourceType.USER_DEFINED)
                print("[i] Renamed %s to %s" % (symbol_name, _new_symbol_name))


def functions_rename(ren_function=True, ren_args=False, ren_local_var=False):
    # type (bool, bool, bool) -> None
    """Rename functions, arguments and local variables

    Args:
        ren_function (bool, optional): rename function to `sub_<hex_value_uppercase>`.
                                        Defaults to True.
        ren_args (bool, optional): rename function's arguments to `a<integer_number>`.
                                        Defaults to False.
        ren_local_var (bool, optional): rename local variables to `var<integer_number>`.
                                        Defaults to False.
    """
    func_manager = currentProgram.getFunctionManager()

    if ren_function:
        for f in func_manager.getFunctions(True):
            function_name = f.getName()
            if not (f.isLibrary()):
                if function_name.startswith("FUN_"):
                    _new_function_name = "sub_" + function_name[len("FUN_") :].upper()
                    f.setName(_new_function_name, SourceType.USER_DEFINED)
                    print(
                        "[i] Renamed fnc: %s to %s"
                        % (function_name, _new_function_name)
                    )

                if ren_args:
                    print("[+] Starting renaming function's arguments ...")
                    args = f.getParameters()
                    for p in args:
                        arg = p.getName()
                        if arg.startswith("param_"):
                            _new_arg_name = "a" + arg[len("param_") :]

                            p.setName(_new_arg_name, SourceType.USER_DEFINED)
                            print(
                                "[i] Renamed parameter: %s to %s in function %s"
                                % (arg, _new_arg_name, function_name)
                            )

                if ren_local_var:
                    print("[+] Starting renaming function's local variables ...")
                    variables = f.getAllVariables()
                    for local_var in variables:
                        str_symbol = local_var.getSymbol().getName()

                        if not str_symbol.startswith("local_res"):
                            # * usually found in pseudo-code view
                            if str_symbol.startswith("local_"):
                                str_symbol_ending = str_symbol[len("local_") :]
                                _symbol = "var" + str_symbol_ending
                                local_var.setName(_symbol, SourceType.USER_DEFINED)
                                print(
                                    "[i] Renamed local var: %s to %s in fnc %s"
                                    % (str_symbol, _symbol, function_name)
                                )
                        else:
                            # * usually found in listing (Assembly) view
                            str_symbol_ending = str_symbol[len("local_res") :]
                            _symbol = "arg_" + str_symbol_ending + "h"
                            local_var.setName(_symbol, SourceType.USER_DEFINED)
                            print(
                                "[i] Renamed local var: %s to %s in fnc %s"
                                % (str_symbol, _symbol, function_name)
                            )
            else:
                print("[ii] Function library %s found, skipping ..." % function_name)


def main():
    # type (None) -> None

    print("[+] Starting renaming global symbols ...")
    globals_rename()
    print("[+] Starting renaming functions ...")
    functions_rename(ren_function=True, ren_args=True, ren_local_var=True)


if __name__ == "__main__":
    main()

