
def prepare_const(data):
    value = str(data)
    value = value.replace("\n", "\\n")
    value = value.replace("\t", "\\t")
    value = value.replace("\r", "\\r")
    value = value.replace("'", "\\'")

    return value

