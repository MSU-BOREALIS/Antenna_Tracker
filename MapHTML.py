def getMapHtml(lat, lon, apiKey):
	""" Generates an HTML and JavaScript code segment using Google Maps API to plot the lat and lon on a map """
	
	maphtml = """
	<!DOCTYPE html>
	<html>
	  <head>
		<meta name="viewport" content="initial-scale=1.0, user-scalable=no">
		<meta charset="utf-8">
		<title>Circles</title>
		<style>
		  html, body {
			height: 100%;
			margin: 0;
			padding: 0;
		  }
		  #map {
			height: 100%;
		  }
		</style>
	  </head>
	  <body>
		<div id="map"></div>
		<script>
		  // This example creates circles on the map

		  // First, create an object containing LatLng and radius for each item.
		  var balloon = {
			payload: {
			  center: {lat: """ + str(lat) + """, lng: """ + str(lon)+"""},
			  rad: 3000
			}
		  };

			function initMap() {
			  var myLatLng = {lat: """+str(lat)+""", lng: """+str(lon)+"""};

			  var map = new google.maps.Map(document.getElementById('map'), {
			    zoom: 8,
			    center: myLatLng
			  });

			  var marker = new google.maps.Marker({
			    position: myLatLng,
			    map: map,
			    title: 'Hello World!'
			  });
			}
		  
		</script>
		<script async defer
		src="https://maps.googleapis.com/maps/api/js?key="""+str(apiKey)+"""&callback=initMap">
		</script>
	  </body>
	</html>
	"""
	return maphtml