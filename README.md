# gha-nbconvert

**Automatically converts only the Jupyter notebooks changed in Pull Request into
readable Python scripts and commits them back to the same branch.**


## How it Works

1. Triggered on **`pull_request`** events (`opened`, `synchronize`, `reopened`,
   limited to `**/*.ipynb` changes).  
2. `executor.py` diffs **`base.sha` … `head.sha`** and collects the notebooks
   modified by the PR.  
3. Each notebook is processed with `jupyter nbconvert --to python`,
   stripped of execution counts / metadata, and written to  
   `output_dir / <source notebook path>`.
4. The resulting files are committed and pushed back to the PR branch.


## Inputs

| Name            | Type (Default)                     | Description                                           |
|-----------------|------------------------------------|-------------------------------------------------------|
| `output_dir`    | _string_ ( `artifacts/gha-nbconvert` ) | Destination folder for generated `.py` files.         |

If the target notebook is `src/notebooks/changed-notebook-name.ipynb` and `output_dir` is `artifacts/gha-nbconvert`, the converted .py file will be output as `artifacts/gha-nbconvert/src/notebooks/changed-notebook-name.py`.


## Quick Start (Workflow Example)

```yaml
name: gha-nbconvert
on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
        - '**/*.ipynb'

jobs:
  gha-nbconvert:
    runs-on: ubuntu-latest
    name: gha-nbconvert
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          fetch-depth: 0
          ref: ${{ github.head_ref }}
      - uses: fractal255/gha-nbconvert@v0.0.4
        with:
          output-dir: "artifacts/gha-nbconvert"
```
