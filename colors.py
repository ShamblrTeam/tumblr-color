# modified from http://charlesleifer.com/blog/using-python-and-k-means-to-find-the-dominant-colors-in-images/

import cStringIO
import urllib
import os
import json
from PIL import Image
from scipy.cluster import vq as sci
from numpy import array
import pytumblr
from pprint import pprint as pp
import psycopg2

# fill this in first
credentials = json.loads(open('tumblr_credentials.json', 'r').read())
tumblr = pytumblr.TumblrRestClient(credentials["consumer_key"],credentials["consumer_secret"],credentials["oauth_token"],credentials["oauth_token_secret"])

def get_points(img):
	points = []
	w, h = img.size
	for count, color in img.getcolors(w * h):
		points.append([color[0],color[1],color[2]])
	return points

rtoh = lambda rgb: '%s' % ''.join(('%02x' % p for p in rgb))

def colorz(img, n=10, trim=32):
	coords = [(x,y) for x in range(img.size[0]) for y in range(img.size[1])]
	
	for coord in coords:
		rgb = img.getpixel(coord)
		pix = (
			(rgb[0]//trim)*trim,
			(rgb[1]//trim)*trim,
			(rgb[2]//trim)*trim
		)
		img.putpixel(coord,pix)
	
	img.thumbnail((200, 200))
	w, h = img.size

	points = array(get_points(img))
	clusters = sci.kmeans(points, n)[0]
	rgbs = [map(int, c) for c in clusters]
	
	return map(rtoh, rgbs)

def main():
	conn_string = "host='localhost' dbname='cs585' user='cs585' "
	db_conn = psycopg2.connect(conn_string)
	cursor = db_conn.cursor()
	limit=100
	offset=2

	while True:
		cursor.execute("SELECT blog_name FROM blog LIMIT %s OFFSET %s;", (limit, limit*offset))

		for record in cursor:
			print record
			#set Target from DB
			target=record[0]
			info = tumblr.blog_info(target)
			try:
				posts = info["blog"]["posts"]
			except:
				continue
			step = 10
			count = 0
			done = False
			colormap = {}

			for notOffset in range(0, posts, step):
				if done:
					break
				#print("{0} - {1}".format(offset,offset+step))
				posts = tumblr.posts(target,limit=step,offset=notOffset)["posts"]
				for post in posts:
					if post["type"] == u'photo':
						for photo in post["photos"]:
							try:
								photolist = photo["alt_sizes"]
								for photo in photolist:
									if photo["width"] == 400:
										url = photo["url"]
								if url == None:
									break
								try:
									f = cStringIO.StringIO(urllib.urlopen(url,timeout=1).read())
									img = Image.open(f)
									colors = colorz(img,trim=32)
										#print(url, colors)
									count = count + 1
								except:
									continue

								for color in colors:
									colormap[color] = colormap.get(color,0) + 1
								if count == 25:
									done = True
							except Exception,e:
								continue
			
			if not colormap:
				continue
			colormap = sorted(colormap, key=colormap.get, reverse=True)
			# for color in colormap:
			# 	print color	

			cursor2 = db_conn.cursor()
			#send to DB
			try:	
				cursor2.execute("insert into colors values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
					(target,
					colormap[0],
					colormap[1],
					colormap[2],
					colormap[3],
					colormap[4],
					colormap[5],
					colormap[6],
					colormap[7],
					colormap[8],
					colormap[9],
					)
					)	
				db_conn.commit()
			except Exception as e:
				print ("DB Fail - ",e)
				db_conn.rollback()

		offset = offset + 1
		print offset
				
	db_conn.commit()
	cursor.close()
	cursor2.close()
	db_conn.close()

if __name__ == "__main__":
	main()
