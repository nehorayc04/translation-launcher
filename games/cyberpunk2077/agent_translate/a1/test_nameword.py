import re
NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")
tests = ["Eva", "Cole", "Preset", "4", "WNS", "News", "Mat", "Duda", "Asa", "Risu", "N54", "Jiro", "Oba", "Mary", "Ann", "Solo", "Set", "Jam", "Sesh"]
for w in tests:
    print(f"{w!r}: {bool(NAMEWORD.match(w))}")
