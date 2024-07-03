
#!/usr/bin/env jupyter
"""
jump_portrait version >=0.0.18
Workflow 1: Fetch one image for a given item and a control
"""
from jump_portrait.fetch import get_jump_image, get_sample
from jump_portrait.save import download_item_images

sample = get_sample()

source, batch, plate, well, site, *rest = sample.row(0)
channel = "DNA"
correction = None # or "Illum"

img = get_jump_image(source, batch, plate, well, channel, site, correction)

"""
Workflow 2: Fetch all images for a given item and their controls
"""

item_name = "MYT1"  # Item or Compound of interest - (GC)OI
# channels = ["bf"]  # Standard channels are ER, AGP, Mito DNA and RNA
channels = ["DNA"]  # Standard channels are ER, AGP, Mito DNA and RNA
corrections = ["Orig"]  # Can also be "Illum"
controls = True  # Fetch controls in plates alongside (GC)OI?

download_item_images(item_name, channels, corrections=corrections, controls=controls)

"""
Workflow 3: Fetch bright field channel
Note that this is hacky and may not work for all sources.
"""
from jump_portrait.fetch import get_jump_image, get_sample
from jump_portrait.save import download_item_images

sample = get_sample()

channel = "bf"
correction = None

source, batch, plate, well, site, *rest = sample.row(0)
img = get_jump_image(source, batch, plate, well, channel, site, correction)
