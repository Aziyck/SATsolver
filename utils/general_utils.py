import os

def clear_console():
    # 'nt' is for Windows, 'posix' is for macOS and Linux
    os.system('cls' if os.name == 'nt' else 'clear')


def indent(level):
    return "  " * level


def var(r, c, v):
    """
    transforma (r,c,v) intr-un numar unic
    ex: (1,2,3) → 123
    """
    return 100*r + 10*c + v