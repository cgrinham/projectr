import random

def rename_image(filename):
	randomstring = random.getrandbits(16)
	filename = filename[:-4] + '_' + str(randomstring) + filename[-4:]
	print filename

rename_image('/christie/file.jpg')