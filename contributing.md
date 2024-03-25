- [Setting up development environments](#org5af6501)
  - [Code Quality](#org5458478)
  - [Formatting](#org799c215)
  - [Linting](#orgafba53a)
  - [Git commit messages](#orgda16adf)
  - [Documentation style guide](#org7778010)

Thanks for considering contributing to our libraries! While the purpose of these are internal use within the Imaging Platform, we welcome bug reports and pull requests.


<a id="org5af6501"></a>

# Setting up development environments

Most of the current libraries are set up using Poetry (you&rsquo;ll see a poetry.lock file inside the lib/<library<sub>name</sub>> folder). You can install them in a local environment using the following lines by replacing <library<sub>name</sub>> with your library of interest.

```bash
# Install Poetry (Linux, MacOS, Windows - WSL)
lib="<library_name>"
curl -sSL https://install.python-poetry.org | python3 -
# Checkout the repository
git clone git@github.com:broadinstitute/monorepo.git
cd libs/<library_name>
poetry install --with dev
```

Note that you must have a python3 installation beforehand. Once that is covered poetry will create a virtual environment inside the project.

We will update this setup by adding Nix installations in the future.


<a id="org5458478"></a>

## Code Quality

Please follow the below quality guides to the best of your abilities. The individual libraries may provide their own pre-commit hooks and additional rules. They usually also contain all of the development tools


<a id="org799c215"></a>

## Formatting

We use [ruff](<https://docs.astral.sh/ruff/>) for formatting Python code. We include \`ruff\` in the poetry dev dependencies so it can be run manually using \`ruff format\`.


<a id="orgafba53a"></a>

## Linting

For python code linting, we also use [ruff](<https://docs.astral.sh/ruff/>), which can perform same linting checks as Flake8. The list of linting rules and exceptions are defined in the \`pyproject.toml\` file under the \`[tool.ruff.lint]\` sections for each librea. If the library you are using contains pre-commit hooks, linting checks will also be run automatically at commit time with the pre-commit hooks as described above.


<a id="orgda16adf"></a>

## Git commit messages

While not strictly enforced, we aim to use [Conventional Commits](<https://www.conventionalcommits.org/en/v1.0.0/>) standard for commit messages to aid in automatic changelog generation.


<a id="org7778010"></a>

## Documentation style guide

guide](<https://numpydoc.readthedocs.io/en/latest/format.html>).
