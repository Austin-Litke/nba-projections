const treatyOakVideos = [
  { title: "No Vacancy", videoId: "NswNzDEWjCY" },
  { title: "New missed call", videoId: "3W61YfdhFlc" },
  { title: "west texas degenerate", videoId: "wI8FmfuS3mc" },
];

let player = null;
let currentIndex = -1;
let triedIndexes = new Set();

function setStatus(text) {
  const el = document.getElementById("music-status");
  if (el) el.textContent = text;
}

function getRandomIndex() {
  return Math.floor(Math.random() * treatyOakVideos.length);
}

function getAnotherIndex(excludeIndex) {
  if (treatyOakVideos.length <= 1) return excludeIndex;

  let index;
  do {
    index = getRandomIndex();
  } while (index === excludeIndex);

  return index;
}

function resetTried() {
  triedIndexes.clear();
}

function tryPlayIndex(index) {
  if (!player) return;

  currentIndex = index;
  triedIndexes.add(index);

  const song = treatyOakVideos[index];
  setStatus(`Trying: ${song.title}`);
  player.loadVideoById(song.videoId);
}

function playRandomSong() {
  if (!player || !treatyOakVideos.length) return;
  resetTried();
  const index = getRandomIndex();
  tryPlayIndex(index);
}

function playNextSong() {
  if (!player || !treatyOakVideos.length) return;
  resetTried();
  const index = getAnotherIndex(currentIndex);
  tryPlayIndex(index);
}

function tryAnotherWorkingSong() {
  if (!player || !treatyOakVideos.length) return;

  if (triedIndexes.size >= treatyOakVideos.length) {
    setStatus("No embeddable songs found in this list.");
    return;
  }

  let nextIndex = getRandomIndex();
  while (triedIndexes.has(nextIndex)) {
    nextIndex = getRandomIndex();
  }

  tryPlayIndex(nextIndex);
}

window.onYouTubeIframeAPIReady = function () {
  player = new YT.Player("yt-player", {
    width: "320",
    height: "200",
    videoId: "NswNzDEWjCY", // always start with the known good one
    playerVars: {
      autoplay: 0,
      rel: 0,
      playsinline: 1
    },
    events: {
      onReady: () => {
        setStatus("Ready to play");

        const playBtn = document.getElementById("music-play-random");
        const nextBtn = document.getElementById("music-next");

        if (playBtn) {
          playBtn.addEventListener("click", () => {
            playRandomSong();
          });
        }

        if (nextBtn) {
          nextBtn.addEventListener("click", () => {
            playNextSong();
          });
        }
      },
      onError: (event) => {
        console.error("YouTube player error:", event.data);
        setStatus("That song cannot be embedded. Trying another...");
        setTimeout(() => {
          tryAnotherWorkingSong();
        }, 400);
      },
      onStateChange: (event) => {
        if (event.data === YT.PlayerState.PLAYING && currentIndex >= 0) {
          setStatus(`Now playing: ${treatyOakVideos[currentIndex].title}`);
        }

        if (event.data === YT.PlayerState.ENDED) {
          resetTried();
          playRandomSong();
        }
      }
    }
  });
};