# @author _raw_data_ @ https://github.com/raw-data
# @category Triage
# @keybinding
# @menupath
# @toolbar

"""
Check current binary's functions against a FunctionIdMatcher database
"""

from ghidra.feature.fid.service import FidService
import json
import os

fm = currentProgram.getFunctionManager()


def generate_function_ids():
    # type (None) -> tuple (str, str, str)
    functions = fm.getFunctions(True)
    for function in functions:
        try:
            function_id = (
                FidService()
                .hashFunction(function)
                .toString()
                .encode("utf-8")
                .split(":")[1]
                .split("(")[0]
                .strip()
            )
        except:
            pass
        else:
            yield (function.getName(), function.getEntryPoint(), "0x" + function_id)


def matching_function(config):
    # type (dict) -> None
    functions_ids_db = config["database"]["functions"]
    for function_name, function_entrypoint, function_id in generate_function_ids():
        if function_id in list(functions_ids_db):

            current_function = fm.getFunctionContaining(function_entrypoint)
            if function_name != functions_ids_db[function_id]:
                current_function.setName(
                    functions_ids_db[function_id],
                    ghidra.program.model.symbol.SourceType.USER_DEFINED,
                )

            print(
                "FunctionEntryPoint: %s\tFunctionID: %s\tOriginalFunctionName: %s\tNewFunctionName: %s"
                % (
                    function_entrypoint,
                    function_id,
                    function_name,
                    functions_ids_db[function_id],
                )
            )


def _load_function_ids_database(config_path):
    # type (str) -> dict
    with open(config_path, "r") as f:
        config = json.loads(f.read())
    return config


def main():
    config = None
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "fiddb.json"
        )
        config = _load_function_ids_database(config_path)
        print("Previous configuration file found @ %s" % config_path)
    except:
        config = askFile("fiddb.json", "Choose a FunctionIdMatcher database")
        import shutil

        shutil.copy2(str(config), config_path)
        config = _load_function_ids_database(config_path)

    matching_function(config)


if __name__ == "__main__":
    main()
