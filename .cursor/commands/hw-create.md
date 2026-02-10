# Create new homework from template (`/hw-create`)

When the user invokes **/hw-create**, create a new homework repository from the template **`fintech-dl-hse/hw-template`** and set it up according to the process in `checkhw/.cursor/rules/homeworks-process-overview.mdc`.

## 1. Get homework name

- If the user provided a name (e.g. `/hw-create my-new-hw` or "create homework foo"), use it. Normalize to a short slug: lowercase, hyphens for spaces (e.g. `my-new-hw`).
- If no name was given, ask: "What should the homework be called? (e.g. `my-topic` → repo `hw-my-topic`, notebook `hw_my_topic.ipynb`)"

## 2. Create the homework repo from template

- Use **GitHub MCP** to create the repository:
  - `mcp_github_create_repository` with `name: "hw-<slug>"`, `organization: "fintech-dl-hse"`, `private: true`, `description` set appropriately.
- Then push the template contents to the new repo:
  - Read the template files from the local **hw-template** workspace folder (or from `fintech-dl-hse/hw-template` on disk if available): `README.md`, `.gitignore`, `.github/.keep`, `.github/workflows/classroom.yml`, `.github/workflows/opencode_review.yml`, `hw_template.ipynb`.
  - Replace in those contents **before** pushing:
    - `hw_template` → `hw_<slug>` (notebook filename: `hw_<slug>.ipynb`)
    - `Template` (workflow name) → `<Display Name>` (e.g. "My New Hw")
    - `autograding-template.json` → `autograding-<slug>.json`
    - In the Extract step: notebook `hw_<slug>.ipynb`; leave `class_definition` and `out_filename` as placeholders or one example — the user will add real extract steps per class.
  - Use **mcp_github_push_files** to push all files to branch `main` of `fintech-dl-hse/hw-<slug>` with message "Initial homework from template: hw-<slug>".

If the workspace does not contain the hw-template folder, use the template repo README and existing homework repos (e.g. hw-mlp, hw-batchnorm) as reference to build the workflow and notebook content for the new repo, then push via GitHub MCP.

## 3. Remind about checkhw setup

After the repo is created, tell the user what they still need to do **in the checkhw repo** (cannot be fully automated without tests and grading config):

- Add **`checkhw/.github/classroom/autograding-<slug>.json`** with test commands and points (copy structure from existing `autograding-*.json`).
- Add **`checkhw/tests/<slug>/`** with pytest tests for the extracted modules.
- Add the homework and **deadline** in **`checkhw/terraform/functions/grades/index.py`** in `known_homeworks`.

Optionally: if the user wants, create a **placeholder** `autograding-<slug>.json` and an empty `tests/<slug>/.keep` in checkhw so the structure is ready (they can fill tests and deadline later).

## 4. Summary

- Reply with the new repo URL: `https://github.com/fintech-dl-hse/hw-<slug>`.
- Mention that they should clone it locally, rename/customize the notebook and workflow (extract steps, runner: `self-hosted-cpu` or `self-hosted-gpu`), add README and `.gitignore` entries for extracted `.py` files, then add tests and autograding config in checkhw as above.

## 5. Notebook authoring checklist (when creating content)

When authoring or editing the homework notebook, follow the rules in **homeworks-process-overview.mdc**:

- **Math**: Use `$ ... $` and `$$ ... $$` only; `\( \)` and `\[ \]` do not render in Jupyter.
- **Structure**: One task per cell; add an “injection” cell if a later cell must `import` something defined in an earlier cell (for both notebook execution and extracted `.py`).
- **Theory**: Cite reference implementation/docs (e.g. PyTorch); describe full algorithm and then “in this assignment” simplified variant.
- **Student version**: Replace solution code with docstring + `raise NotImplementedError("...")`; keep names and signatures unchanged.
- **Tests**: Optionally add a cell that runs the same checks as `checkhw/tests/<slug>/` so students can run tests in the notebook.

## Reference

- Process and notebook structure: **`checkhw/.cursor/rules/homeworks-process-overview.mdc`**
- Template repo: **https://github.com/fintech-dl-hse/hw-template**
- Workflow runner tags: use **`self-hosted-cpu`** or **`self-hosted-gpu`** only (never plain `self-hosted`).
