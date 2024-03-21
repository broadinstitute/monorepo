
# Table of Contents

1.  [Decision Flowchart](#org9b56f55)
2.  [Quick data access](#orga6eaec3)
3.  [Overview](#orgd47e176)
4.  [Data accessibility](#orgb127634)
5.  [Installation](#org348a90d)
    1.  [pip](#orgfc5390b)
    2.  [poetry (dev)](#orgfcdba6d)
6.  [Contributions](#org880ec80)



<a id="org9b56f55"></a>

# Decision Flowchart

    flowchart LR
        A[Start] --> B{What kind of data do I have?}
        B -- Chemicals --> C[(WIP)]
        B -- Genes --> D{What kind of genetic perturbation?}
        B -- Genes and Chemicals --> asd[(WIP)]
        B -- None, I just want to explore images --> images[broad.io/gallery]
        D -- Overexpression --> orf{Are you looking for specific features?}
        D -- Knock-out --> crispr{Are you looking for specific features?}
        orf -- No -->  F[(broad.io/orf)]
        orf -- Yes -->  G[(broad.io/orf_feature)]
        crispr -- No -->  H[(broad.io/crispr)]
        crispr -- Yes --> I[(WIP)]


<a id="orga6eaec3"></a>

# Quick data access

Use the following datasets to explore morphological similarities between gene and/or compounds.

<table border="2" cellspacing="0" cellpadding="6" rules="groups" frame="hsides">


<colgroup>
<col  class="org-left" />

<col  class="org-left" />

<col  class="org-left" />

<col  class="org-left" />

<col  class="org-left" />
</colgroup>
<thead>
<tr>
<th scope="col" class="org-left">Dataset</th>
<th scope="col" class="org-left">Perturbation simile</th>
<th scope="col" class="org-left">Feature ranking</th>
<th scope="col" class="org-left">Gallery</th>
<th scope="col" class="org-left">Description</th>
</tr>
</thead>

<tbody>
<tr>
<td class="org-left">ORF</td>
<td class="org-left"><a href="https://broad.io/orf">broad.io/orf</a></td>
<td class="org-left"><a href="https://broad.io/orf_feature">broad.io/orf_feature</a></td>
<td class="org-left">WIP</td>
<td class="org-left">Gene overexpression</td>
</tr>


<tr>
<td class="org-left">CRISPR</td>
<td class="org-left"><a href="https://broad.io/crispr">broad.io/crispr</a></td>
<td class="org-left">WIP</td>
<td class="org-left"><a href="https://broad.io/crispr_gallery">broad.io/crispr_gallery</a></td>
<td class="org-left">Gene knock-out</td>
</tr>


<tr>
<td class="org-left">Compound</td>
<td class="org-left">WIP</td>
<td class="org-left">WIP</td>
<td class="org-left">WIP</td>
<td class="org-left">Chemical compounds</td>
</tr>
</tbody>
</table>

Note that the feature databases are based on interpretable features. The The perturbation databases use non-interpretable features, which increase sample replicability.


<a id="orgd47e176"></a>

# Overview

This module provides tools to efficiently compare vectors of [JUMP](https://jump-cellpainting.broadinstitute.org/) data. It also assembles the dataframes that are to be accessed by biologists using [datasette-lite](https://github.com/simonw/datasette-lite).


<a id="orgb127634"></a>

# Data accessibility

The raw morphological profiles are currently in a local server. It will be provided independently and this section updated in the future.


<a id="org348a90d"></a>

# Installation

You do not need to install this unless you want to re-do the similarity calculations. You can use the datasette web interface provided if your goal is to explore genes. We assume that a GPU and cuda11 are available in the server where this is run. This is to use cupy, which offers vastly faster distance calculations.


<a id="orgfc5390b"></a>

## pip

Use this if you want to analyse data.

    pip install jump_rr


<a id="orgfcdba6d"></a>

## poetry (dev)

Use this if you want to tweak the functions

    git clone https://github.com/broadinstitute/monorepo/
    cd monorepo/libs/jump_rr
    poetry install --with dev


<a id="org880ec80"></a>

# Contributions

Feel free to open an bug/request issue or submit a pull request with the `jump_rr` tag.

