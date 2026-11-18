# ADR 009: DTO Validation Format

**Status:** Accepted  
**Context:** Task #22 (Error handling and validation). Strict validation of incoming data from the user interface (file paths, passwords) became necessary. Migrating DTOs to `Pydantic v2` was considered.  

## Decision
Do not adopt `Pydantic` at the current stage of the project lifecycle.
Keep DTOs as `@dataclass(frozen=True)` from the Python standard library, and implement validation manually through the built-in `__post_init__` mechanism.

## Rationale
1. **No external API:** The application is a desktop solution (PyQt6). Data is built programmatically inside the application and does not arrive as untyped JSON from the outside world, so `pydantic`'s powerful type-coercion mechanism is unnecessary.
2. **Minimize External Dependencies:** Adding `Pydantic v2` pulls in the binary dependency `pydantic-core` (Rust), which can complicate the build and increase the distribution size.
3. **YAGNI (You Aren't Gonna Need It):** Adopting a tool "for future growth" breaks the existing immutability test suite and requires reworking error handling for a doubtful benefit. 

## Consequences (Implementation Implications)
* Validation runs inside `def __post_init__(self):`.
* Business-logic and contract errors must raise standard Python exceptions (`ValueError`, `FileNotFoundError`), which are caught in the UI layer or when the worker is initialized.
* Any field mutation inside `__post_init__` (for example, normalizing paths) must use a workaround: `object.__setattr__(self, 'field', val)`, because `frozen=True` is set.
