
# Table of Contents

1.  [Quick data access](#org3e5187d)
2.  [Overview](#orgb5b5c25)
3.  [Data accessibility](#orgbf4f464)
4.  [Installation](#org6201052)
    1.  [pip](#org8b6fe5d)
    2.  [poetry (dev)](#orgcf613bf)
5.  [Contributions](#org5068f8c)



<a id="org3e5187d"></a>

# Quick data access

Use the following datasets to explore morphological similarities between gene and/or compounds.

<table border="2" cellspacing="0" cellpadding="6" rules="groups" frame="hsides">


<colgroup>
<col  class="org-left" />

<col  class="org-left" />

<col  class="org-left" />

<col  class="org-left" />
</colgroup>
<thead>
<tr>
<th scope="col" class="org-left">Dataset</th>
<th scope="col" class="org-left">Perturbation simile</th>
<th scope="col" class="org-left">Feature simile</th>
<th scope="col" class="org-left">Description</th>
</tr>
</thead>

<tbody>
<tr>
<td class="org-left">ORF</td>
<td class="org-left"><a href="https://broad.io/orf">broad.io/orf</a></td>
<td class="org-left">TBD</td>
<td class="org-left">Gene overexpression</td>
</tr>


<tr>
<td class="org-left">CRISPR</td>
<td class="org-left"><a href="https://broad.io/crispr">broad.io/crispr</a></td>
<td class="org-left">TBD</td>
<td class="org-left">Gene knock-out</td>
</tr>


<tr>
<td class="org-left">Compound</td>
<td class="org-left">TBD</td>
<td class="org-left">TBD</td>
<td class="org-left">Chemical compound</td>
</tr>
</tbody>
</table>


<a id="orgb5b5c25"></a>

# Overview

This module provides tools to efficiently compare vectors of [JUMP](https://jump-cellpainting.broadinstitute.org/) data. It also assembles the dataframes that are to be accessed by biologists using [datasette-lite](https://github.com/simonw/datasette-lite).


<a id="orgbf4f464"></a>

# Data accessibility

The raw morphological profiles are currently in a local server. It will be provided independently and this section updated in the future.


<a id="org6201052"></a>

# Installation

You do not need to install this unless you want to re-do the similarity calculations. You can use the datasette web interface provided if your goal is to explore genes. We assume that a GPU and cuda11 are available in the server where this is run. This is to use cupy, which offers vastly faster distance calculations.


<a id="org8b6fe5d"></a>

## pip

Use this if you want to analyse data.

    pip install jump_rr


<a id="orgcf613bf"></a>

## poetry (dev)

Use this if you want to tweak the functions

    git clone https://github.com/broadinstitute/monorepo/
    cd monorepo/libs/jump_rr
    poetry install --with dev


<a id="org5068f8c"></a>

# Contributions

Feel free to open an bug/request issue or submit a pull request with the `jump_rr` tag.

