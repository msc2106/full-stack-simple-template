from typing import Any

from sqlalchemy.orm import selectinload


class AlreadyExistsError(Exception):
    pass


def prepare_selectinload_options(*rel_specs: Any) -> list:
    options: list = []
    for rel in rel_specs:
        match rel:
            case list() as rel_chain:
                options.append(selectinload_chain(*rel_chain))
            case (rel, int() as recursion_depth):
                if not isinstance(recursion_depth, int) or recursion_depth < 1:
                    raise ValueError(
                        "Invalid recursion depth "
                        + f"{recursion_depth} for relationship {rel}"
                    )
                options.append(selectinload(rel, recursion_depth=recursion_depth))
            case _:
                options.append(selectinload(rel))
    return options


def selectinload_chain(*rels):
    if len(rels) == 0:
        raise ValueError("At least one relationship must be specified")
    load_chain = selectinload(rels[0])
    for rel in rels[1:]:
        load_chain = load_chain.selectinload(rel)
    return load_chain
