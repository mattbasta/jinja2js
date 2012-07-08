
def prepare_const(data):
    value = data.replace("\n", "\\n")
    value = value.replace("\t", "\\t")
    value = value.replace("\r", "\\r")
    value = value.replace("'", "\\'")

    return data

