"""Paths locais centralizados; o MVP mantém saídas dentro do repositório."""
from pathlib import Path

import yaml


def load_paths(repo_root: Path) -> dict[str, Path]:
    root = repo_root.resolve()
    config = root / "configs" / "paths.yaml"
    document = yaml.safe_load(config.read_text(encoding="utf-8-sig")) if config.exists() else {}
    if not isinstance(document, dict) or set(document) - {"repo_root", "data", "docs"}:
        raise ValueError("Configuração de paths inválida")
    if document.get("repo_root", ".") != ".":
        raise ValueError("repo_root deve ser '.'; a raiz é definida pelo entrypoint")
    data = document.get("data", {})
    docs = document.get("docs", {})
    if not isinstance(data, dict) or set(data) - {"raw", "bronze", "silver", "gold", "sample", "events"}:
        raise ValueError("Seção data inválida em paths.yaml")
    if not isinstance(docs, dict) or set(docs) - {"root", "data_dictionary", "data_quality", "lineage", "observability"}:
        raise ValueError("Seção docs inválida em paths.yaml")

    def local(value):
        if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
            raise ValueError("Paths devem ser strings relativas não vazias")
        path = (root / value).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Path deve permanecer dentro do repositório, abaixo da raiz")
        return path

    result = {f"{layer}_dir": local(data.get(layer, 'data/samples' if layer == 'sample' else f"data/{layer}"))
              for layer in ("raw", "bronze", "silver", "gold", "sample", "events")}
    layers = list(result.values())
    if any(a.is_relative_to(b) or b.is_relative_to(a)
           for index, a in enumerate(layers) for b in layers[index + 1:]):
        raise ValueError("Camadas de dados não podem compartilhar ou conter caminhos umas das outras")
    docs_root = docs.get("root", "docs")
    result["docs_root"] = local(docs_root)
    for name, suffix in {"data_dictionary": "data_dictionary/tables", "data_quality": "data_quality",
                         "lineage": "lineage", "observability": "observability"}.items():
        result[f"{name}_dir"] = local(docs.get(name, f"{docs_root}/{suffix}"))
    return result
