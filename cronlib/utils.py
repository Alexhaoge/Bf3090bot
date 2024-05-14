def str_to_bool(s: str) -> bool:
    if s.lower() in ('true', '1', 't', 'y', 'yes'):
        return True
    elif s.lower() in ('false', '0', 'f', 'n', 'no'):
        return False
    else:
        raise ValueError(f"Cannot covert {s} to a bool")