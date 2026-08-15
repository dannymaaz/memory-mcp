from dataclasses import dataclass


@dataclass(frozen=True)
class Budget:
    limit: int
    margin: float = 0.08

    @property
    def effective(self) -> int:
        return int(self.limit * (1.0 - self.margin))


def select_items(items: list[dict[str, object]], budget: Budget) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for item in sorted(items, key=lambda value: float(value.get("score", 0)), reverse=True):
        if len(selected) >= budget.effective:
            break
        selected.append(item)
    return selected
