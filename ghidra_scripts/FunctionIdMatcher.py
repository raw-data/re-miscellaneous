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


def get_best_matching_datatype(datatype, name, dataTypeManager):
    candidates = []
    datatype = dataTypeManager.findDataTypes(name, candidates)
    if len(candidates) == 1:
        datatype = candidates[0]
    return datatype


def deserialize_arguments(parameters, arguments, program):
    dataTypeManager = program.getDataTypeManager()
    for idx, argument in enumerate(arguments):
        # TODO: handle if not all parameters were detected (i.e. the parameter code
        # of "parameters" is smaller than the length of "arguments")
        newDataType = get_best_matching_datatype(
            parameters[idx].getDataType(),
            argument["type"], dataTypeManager
        )

        newAdress = parameters[idx].getVariableStorage().getVarnodes()[0].getAddress()

        parameters[idx] = ghidra.program.model.listing.ParameterImpl(
            argument["name"], newDataType, newAdress, program)
    return parameters


def matching_function(config):
    # type (dict) -> None
    functions_ids_db = config["database"]["functions"]

    program = getState().getCurrentProgram()
    dataTypeManager = program.getDataTypeManager()

    for function_name, function_entrypoint, function_id in generate_function_ids():
        if function_id in list(functions_ids_db):

            current_function = fm.getFunctionContaining(function_entrypoint)
            if function_name != functions_ids_db[function_id]["name"]:

                current_function.setName(
                    functions_ids_db[function_id]["name"],
                    ghidra.program.model.symbol.SourceType.USER_DEFINED,
                )

                arguments = deserialize_arguments(
                    current_function.getParameters(),
                    functions_ids_db[function_id]["arguments"],
                    program
                )

                current_function.replaceParameters(
                    ghidra.program.model.listing.Function.FunctionUpdateType.DYNAMIC_STORAGE_FORMAL_PARAMS,
                    0,
                    ghidra.program.model.symbol.SourceType.ANALYSIS,
                    arguments
                )

                newReturnDatatype = get_best_matching_datatype(
                    current_function.getReturn().getDataType(),
                    functions_ids_db[function_id]["return"]["type"],
                    dataTypeManager
                )
                current_function.setReturn(
                    newReturnDatatype,
                    current_function.getReturn().getVariableStorage(),
                    ghidra.program.model.symbol.SourceType.ANALYSIS
                )

                print(
                    "FunctionEntryPoint: %s\tFunctionID: %s\tOriginalFunctionName: %s\tNewFunctionName: %s"
                    % (
                        function_entrypoint,
                        function_id,
                        function_name,
                        functions_ids_db[function_id]["name"],
                    )
                )
            else:
                print(
                    "FunctionEntryPoint: %s\tFunctionID: %s\tKeptFunctionName: %s"
                    % (
                        function_entrypoint,
                        function_id,
                        function_name,
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
