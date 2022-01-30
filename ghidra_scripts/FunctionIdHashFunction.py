# @author _raw_data_ @ https://github.com/raw-data
# @category Triage
# @keybinding Shift H
# @menupath
# @toolbar

"""
Generate a FunctionID hash of a selected function
"""

from ghidra.feature.fid.service import FidService
from collections import OrderedDict
from datetime import datetime
import json
import os


class FunctionIdDb(object):
    def __init__(self, config_path):
        self.DB_SCHEMA = OrderedDict(
            {
                "version": "0.1",
                "database": {"entries": 0, "last_update_utc": "", "functions": {}},
            }
        )
        self.config_path = config_path

    def init_database(self):
        with open(self.config_path, "w") as f:
            f.write(json.dumps(self.DB_SCHEMA, indent=2))

    def load_database(self):
        with open(self.config_path, "r") as f:
            db = json.loads(f.read())
        return db

    def update_database(self, new_entires):
        # type (list) -> None
        current_db = self.load_database()
        selected_new_functions_ids = list()
        for entry in new_entires:
            for new_function_id_hash in list(entry):
                if new_function_id_hash not in list(
                    current_db["database"]["functions"]
                ):
                    print(
                        "[+] FunctionName: %s\tFunctionID: %s added to database"
                        % (entry.values()[0]["name"], entry.keys()[0])
                    )
                    current_db["database"]["functions"].update(entry)
                else:
                    print(
                        "[i] FunctionName: %s with FunctionID: %s is already known to the current database, skipping ..."
                        % (entry.values()[0]["name"], entry.keys()[0])
                    )
        current_db["database"]["entries"] = len(
            list(current_db["database"]["functions"])
        )

        current_db["database"]["last_update_utc"] = datetime.utcnow().isoformat()

        with open(self.config_path, "w") as f:
            f.write(json.dumps(current_db, indent=2))


def serialize_varnodes(varnodes):
    if len(varnodes) == 0:
        return None
    varnode = varnodes[0]
    return {"address": varnode.getAddress().getAddressSpace().getName()+":"+str(varnode.getAddress().getOffset()), "size": varnode.getSize()}


def generate_function_id_hash(db):
    # type (FunctionIdDb) -> None
    fn = getFunctionContaining(currentAddress)
    fn_address = fn.getBody().getMinAddress()
    try:
        function_id = (
            FidService()
            .hashFunction(fn)
            .toString()
            .encode("utf-8")
            .split(":")[1]
            .split("(")[0]
            .strip()
        )
    except:
        print(
            "[!] Cannot generate a FunctionID hash from function %s @ %s"
            % (fn_address, fn.getName())
        )
    else:
        arguments = []
        for p in fn.getParameters():
            arguments.append({
                "name": p.getName(),
                "type": p.getDataType().getName(),
                "storage": serialize_varnodes(p.getVariableStorage().getVarnodes())
            })
        db.update_database([{
            "0x" + function_id: {
                "name": fn.getName(),
                "arguments": arguments,
                "return": {
                    "type": fn.getReturn().getDataType().getName(),
                    "storage": serialize_varnodes(fn.getReturn().getVariableStorage().getVarnodes())
                }
            }
        }])


def main():
    config_path = None
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "fiddb.json"
        )
        print("Previous configuration file found @ %s" % config_path)
        db = FunctionIdDb(config_path)
        db.load_database()
    except:
        print("[!] No previous database found! creating one @ %s" % config_path)
        db = FunctionIdDb(config_path)
        db.init_database()

    generate_function_id_hash(db)


if __name__ == "__main__":
    main()
