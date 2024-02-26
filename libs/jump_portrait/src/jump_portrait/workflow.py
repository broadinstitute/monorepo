#!/usr/bin/env jupyter
"""
Workflow 1: Fetch one image for a given item and a control
"""
from jump_portrait.fetch import get_jump_image, get_sample
from jump_portrait.save import download_item_images

sample = get_sample()

source, batch, plate, well, site, *rest = sample.row(0)
channel = "DNA"
correction = "Illum"

img = get_jump_image(source, batch, plate, well, channel, site, correction)

"""
Workflow 2: Fetch all images for a given item and their controls
"""

item_name = "MYT1"  # Item or Compound of interest - (GC)OI
channels = ["DNA"]  # Standard channels are ER, AGP, Mito DNA and RNA
corrections = ["Orig"]  # Can also be "Illum"
controls = True  # Fetch controls in plates alongside (GC)OI?

download_item_images(item_name, channels, corrections=corrections, controls=controls)
