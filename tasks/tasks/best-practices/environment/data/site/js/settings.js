const statusNode = document.getElementById('location-status');
const locationButton = document.getElementById('use-location');

function usePosition(position) {
  statusNode.innerHTML = `Location received: ${position.coords.latitude}, ${position.coords.longitude}`;
}

function locationFailed(error) {
  console.log(error);
}

navigator.geolocation.getCurrentPosition(usePosition, locationFailed);
window.addEventListener('resize', () => console.log('resized'));
