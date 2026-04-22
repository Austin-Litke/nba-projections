let spotifyController = null;

// Treaty Oak Revival song/artist testing will need a real Spotify URI.
// For now this can be any valid Spotify track URI.
const spotifyTestTrackUri = "spotify:track:11dFghVXANMlKmJXsNCbNl";

function setSpotifyStatus(text) {
  const el = document.getElementById("spotify-status");
  if (el) el.textContent = text;
}

window.onSpotifyIframeApiReady = (IFrameAPI) => {
  const element = document.getElementById("spotify-embed");
  if (!element) return;

  const options = {
    uri: spotifyTestTrackUri,
    width: "100%",
    height: 152
  };

  const callback = (EmbedController) => {
    spotifyController = EmbedController;
    setSpotifyStatus("Spotify embed loaded");

    spotifyController.addListener("ready", () => {
      setSpotifyStatus("Spotify player ready");
      console.log("[spotify-debug] ready");
    });

    spotifyController.addListener("playback_update", (e) => {
      console.log("[spotify-debug] playback_update", e.data);
    });

    const btn = document.getElementById("spotify-test-btn");
    if (btn) {
      btn.addEventListener("click", () => {
        setSpotifyStatus("Trying Spotify playback...");
        spotifyController.play();
      });
    }
  };

  IFrameAPI.createController(element, options, callback);
};