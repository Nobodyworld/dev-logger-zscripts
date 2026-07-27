"""Purpose-built raw metric fixture."""


def complex_target(alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota):
    if alpha and beta and gamma:
        for value in delta:
            while value:
                try:
                    value -= 1
                except ValueError:
                    break
    selected = [value for value in epsilon if value]
    return selected if zeta else [eta, theta, iota]


def deeply_nested(value):
    if value:
        if value:
            if value:
                if value:
                    if value:
                        if value:
                            return value
    return None


def orphan_candidate():
    return "static analysis cannot prove this is unused"
