1. You'll need to install some python modules (pillow for image processing and several modules from google.

you can install them using requirements.txt file and pip, somethig like that:

python3 -m pip install -r ./requirements.txt

2. make sure the script works:

run something like 
# python3 ./img_overlay_gdrive.py list
it will show a list of files in google drive folder Image_mods

this is how it looks on my machine:
$ ./img_overlay_gdrive.py list
Directory Image_mods -> 1DN5atvwNS7HPgI6eIVSnVsm1MgY75hDi content:

final_Designer.jpeg -> 1qT3bxoy1bS8h9ACQ3z_gNW40dnCDhpdx
Designer.jpeg -> 1FDNfdCavnzLRvwD5wZ6s_yir-uf-UEVa
10373.jpg -> 1OK_51vgWYXOF2DwASBdhqu9K2bB6IaOR

3. run the script using "overlay" command

python3 ./img_overlay_gdrive.py overlay Designer.jpeg 10373.jpg -c 0.5,0.5 -s 0.1
arguments: 
Designer.jpeg: host image
10373.jpg: guest image
-c 0.5,0.5: center position (x,y) 0 means left or top, 1 right or bottom
-s 0.1: size factor of the guest image 
