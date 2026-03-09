- [Setting up development environments](#Setting%20up%20development%20environments)
  - [Code Quality](#Code%20Quality)
  - [Formatting and linting](#Formatting%20and%20linting)
  - [Git commit messages](#Git%20commit%20messages)
  - [Documentation style guide](#Documentation%20style%20guide)
  - [Code reviews](#Code%20reviews)

Thanks for considering contributing to our libraries! While the purpose of these are internal use within the Imaging Platform, we welcome bug reports and pull requests.


<a id="Setting%20up%20development%20environments"></a>

# Setting up development environments

We use uv for development, just cd to the libs/PROJECT folder and run `uv sync --all-groups`. If Nix is available, `nix develop .` should be enough.

<a id="Code%20Quality"></a>

## Code Quality

Please follow the below quality guides to the best of your abilities. The individual libraries may provide their own pre-commit hooks and additional rules. They usually also contain all of the standard development tools we use.

We prefer modules and scripts over jupyter notebooks. While these are not fully banned, they can be usually avoided by using an interactive development environment and the [jupytext](https://jupytext.readthedocs.io/en/latest/) library to convert python scripts to other formats. If using this system, the prefered separator for blocks is py:percent.


<a id="Formatting%20and%20linting"></a>

## Formatting and linting

We use [ruff](https://docs.astral.sh/ruff/) for formatting and linting Python code. In projects that use poetry, we include \`ruff\` (and \`ruff-lsp\` where applicable) as dev dependencies so it can be run manually using \`ruff format\`. We use the default rules, but this may change in the future.

The list of linting rules and exceptions are defined in the \`pyproject.toml\` file under the \`[tool.ruff.lint]\` sections for each library. If the library you are using contains pre-commit hooks, linting checks will also be run automatically at commit time with the pre-commit hooks as described above.


<a id="Git%20commit%20messages"></a>

## Git commit messages

While not strictly enforced, we suggest using the [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) standard for commit messages to aid in automatic changelog generation.


<a id="Documentation%20style%20guide"></a>

## Documentation style guide

We use numpy documentation style (see [guide](https://numpydoc.readthedocs.io/en/latest/format.html)).


<a id="Code%20reviews"></a>

## Code reviews

We follow multiple rules of the thumb on how to review code to maintain high quality for our libraries and the reproducibility of our results. Consider these points when reviewing others&rsquo; code or requesting one. You can read more on anti-patterns [here](https://github.com/quantifiedcode/python-anti-patterns/blob/master/docs/The-Little-Book-Of-Python-Anti-Patterns.pdf). Objects NOT to commit:

-   Binaries: They cannot be version-controlled.
-   Large files (>10MB): They slow down the repository.
-   Do not push notebooks to the modules: They are hard to parse, obscure diffs and are much bigger than the equivalent script.
-   Data: the only exception is tiny (<1MB) datasets for tests, but try to generate it as [pytest fixtures](https://docs.pytest.org/en/stable/reference/fixtures.html) instead if possible.

Observed anti-patterns to avoid:

-   One function can return multiple types of output.
-   Paths to local files: For full reproducibility we need to be able to access the data when it is publicly available. The exceptions for this are tutorial-like scripts and data that is not yet public. In the latter case use instead a folder present in the data location (e.g., our server&rsquo;s shared storage); add a comment to the url of the private repo pointing to the original files. This will simplify the refactoring when making the data public and ensure that the results are reproducible.
-   Sample data contains unnecessary information: Everything not necessary to test the functionality of a component is noise, avoid commiting such type of data.
-   Overusing Try-Except: This may make your code run but it may obscure edge-cases that bring bugs out to the open.

Things that makes us happy:

-   Lock your dependencies: Regardless of the library you use, please ensure you lock your libraries (e.g., uv.lock) to ensure others can reproduce your environment.
-   Document and specify the type all inputs and outputs: This makes code much easier to maintain over time.

