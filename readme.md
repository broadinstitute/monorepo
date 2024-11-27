- [Table of Contents](#Table%20of%20Contents)
  - [Tools](#Tools)
    - [Libraries](#Libraries)
    - [To be integrated](#To%20be%20integrated)
  - [JUMP Information Central](#JUMP%20Information%20Central)
  - [Contributing](#Contributing)



<a id="Table%20of%20Contents"></a>

# Table of Contents

Documentation under construction. This is intended to concentrate all the shared tools of the Carpenter-Singh Lab, part of the Broad Institute&rsquo;s Imaging Platform.


<a id="Tools"></a>

## Tools


<a id="Libraries"></a>

### Libraries

-   [broad\_babel](https://github.com/broadinstitute/monorepo/tree/main/libs/jump_babel): Translate gene names to and from broad and JUMP ids, NCBI and other identifiers.
-   [jump\_compound\_annotator](https://github.com/broadinstitute/monorepo/tree/main/libs/jump_compound_annotator): Collect compound names and relationships from multiple online databases using their APIs or web requests.
-   [jump\_portrait](https://github.com/broadinstitute/monorepo/tree/main/libs/jump_portrait): Fetch JUMP images from CellPainting&rsquo;s AWS servers. It also contains some utilities to explore file names.
-   [jump\_rr](https://github.com/broadinstitute/monorepo/tree/main/libs/jump_rr): Generate browsable databases of perturbation similarities and morphological feature rankings to be explored and queried on a browser.
-   [trommel](https://github.com/broadinstitute/monorepo/tree/main/libs/trommel): Data-cleaning functions and pipelines to improve the signal of morphological profiles.
-   [jump\_smiles](https://github.com/broadinstitute/monorepo/tree/swb/libs/smiles): Standardiser of (Chemical) SMILES.

1.  Under development

    -   [kaljax](https://github.com/broadinstitute/monorepo/tree/b9c5953f64a6f2d5da1f968ef748e5e122b804c0/libs/kaljax/README.md): High efficiency single cell tracker using CellProfiler features and a Kalman filter, it aims to support both on CPUs and GPUs.


<a id="To%20be%20integrated"></a>

### Other tools/libraries

-   [copairs](https://github.com/broadinstitute/2023_12_JUMP_data_only_vignettes/tree/master): Find pairs and compute metrics between them.


<a id="JUMP%20Information%20Central"></a>

## JUMP Information Central

JUMP Cell Painting is one of our main projects, it is the creation of a data-driven approach to drug discovery based on cellular imaging, image analysis, and high dimensional data analytics You can find general information [here](https://jump-cellpainting.broadinstitute.org/), and details on how to make use of it [here](https://broad.io/jump).


<a id="Contributing"></a>

## Contributing

See [contributing.md](./contributing.md) for details.
