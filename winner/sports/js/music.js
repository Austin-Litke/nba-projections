const treatyOakVideos = [
  { title: "No Vacancy", videoId: "NswNzDEWjCY" },
  { title: "New Missed Call", videoId: "3W61YfdhFlc" },
  { title: "West Texas Degenerate", videoId: "wI8FmfuS3mc" },
  { title: "Ode to bourbon", videoId: "sm9DMdQUNWA" },
  { title: "Fishnets", videoId: "7SoTY0jhOSg" },
  { title: "In Between", videoId: "FixEIfSCNT0" },
  { title: "Stop & Stare", videoId: "Uc12NL0HN7w" },
  { title: "Have a nice Day", videoId: "BaI6qEdFqR8" },
  { title: "Bad State of Mind", videoId: "rE-4FDZnXDw" },
  { title: "Happy Face", videoId: "ZoCEGAcR6zM" },
  { title: "Withdrawals", videoId: "3PlHurzjC4k" },
];

const testVideos = [
  { title: "Cage The Elephant - Ain't No Rest", videoId: "HKtsdZs9LJo" },
  { title: "Cage The Elephant - Cigarette Daydreams", videoId: "vAu4WIK-VfM" },
  { title: "Arctic Monkeys - Do I Wanna Know", videoId: "bpOSxM0rNPM" },
  { title: "The Neighbourhood - Sweater Weather", videoId: "GCdwKhTtNNw" },
  { title: "Glass Animals - Heat Waves", videoId: "mRD0-GxqHVo" },
];

let player = null;
let currentPlaylist = treatyOakVideos;
let currentPlaylistName = "Treaty Oak Revival";
let currentIndex = 0;
let triedIndexes = new Set();

function setStatus(text) {
  const el = document.getElementById("music-status");
  if (el) el.textContent = text;
}

function getRandomIndex() {
  return Math.floor(Math.random() * currentPlaylist.length);
}

function getAnotherIndex(excludeIndex) {
  if (currentPlaylist.length <= 1) return excludeIndex;

  let index;
  do {
    index = getRandomIndex();
  } while (index === excludeIndex);

  return index;
}

function resetTried() {
  triedIndexes.clear();
}

function populateDropdown(selectId, songs) {
  const select = document.getElementById(selectId);
  if (!select) return;

  select.innerHTML = '<option value="">Choose a song</option>';

  songs.forEach((song, index) => {
    const option = document.createElement("option");
    option.value = index;
    option.textContent = song.title;
    select.appendChild(option);
  });
}

function tryPlayIndex(index) {
  if (!player) return;
  if (index < 0 || index >= currentPlaylist.length) return;

  currentIndex = index;
  triedIndexes.add(index);

  const song = currentPlaylist[index];
  console.log("Current playlist:", currentPlaylistName);
  console.log("Current song:", song);

  setStatus(`Trying (${currentPlaylistName}): ${song.title}`);
  player.loadVideoById(song.videoId);
}

function playRandomSong() {
  if (!player || !currentPlaylist.length) return;
  resetTried();
  tryPlayIndex(getRandomIndex());
}

function playNextSong() {
  if (!player || !currentPlaylist.length) return;
  resetTried();
  tryPlayIndex(getAnotherIndex(currentIndex));
}

function tryAnotherWorkingSong() {
  if (!player || !currentPlaylist.length) return;

  if (triedIndexes.size >= currentPlaylist.length) {
    setStatus(`No embeddable songs found in ${currentPlaylistName}`);
    return;
  }

  let nextIndex = getRandomIndex();
  while (triedIndexes.has(nextIndex)) {
    nextIndex = getRandomIndex();
  }

  tryPlayIndex(nextIndex);
}

function switchToPlaylist(playlist, playlistName) {
  currentPlaylist = playlist;
  currentPlaylistName = playlistName;
  currentIndex = 0;
  resetTried();
  setStatus(`Switched to ${playlistName}`);
}

function playSelectedTreatySong() {
  const select = document.getElementById("treaty-select");
  if (!select || select.value === "") {
    setStatus("Choose a Treaty Oak song first.");
    return;
  }

  switchToPlaylist(treatyOakVideos, "Treaty Oak Revival");
  tryPlayIndex(Number(select.value));
}

function playSelectedTestSong() {
  const select = document.getElementById("cash-select");
  if (!select || select.value === "") {
    setStatus("Choose a test song first.");
    return;
  }

  switchToPlaylist(testVideos, "Test Playlist");
  tryPlayIndex(Number(select.value));
}

window.onYouTubeIframeAPIReady = function () {
  player = new YT.Player("yt-player", {
    width: "320",
    height: "200",
    videoId: treatyOakVideos[0].videoId,
    playerVars: {
      autoplay: 0,
      rel: 0,
      playsinline: 1
    },
    events: {
      onReady: () => {
        populateDropdown("treaty-select", treatyOakVideos);
        populateDropdown("cash-select", testVideos);

        setStatus("Ready to play");

        const nextBtn = document.getElementById("music-next");
        const treatyBtn = document.getElementById("music-play-treaty");
        const testBtn = document.getElementById("music-play-cash");
        const treatySelectedBtn = document.getElementById("music-play-treaty-selected");
        const testSelectedBtn = document.getElementById("music-play-cash-selected");

        if (nextBtn) {
          nextBtn.addEventListener("click", playNextSong);
        }

        if (treatyBtn) {
          treatyBtn.addEventListener("click", () => {
            switchToPlaylist(treatyOakVideos, "Treaty Oak Revival");
            playRandomSong();
          });
        }

        if (testBtn) {
          testBtn.addEventListener("click", () => {
            switchToPlaylist(testVideos, "Test Playlist");
            playRandomSong();
          });
        }

        if (treatySelectedBtn) {
          treatySelectedBtn.addEventListener("click", playSelectedTreatySong);
        }

        if (testSelectedBtn) {
          testSelectedBtn.addEventListener("click", playSelectedTestSong);
        }
      },

      onError: (event) => {
        const badSong = currentPlaylist[currentIndex];
        console.error("YouTube error:", event.data, badSong);
        setStatus(`"${badSong?.title || "Unknown song"}" can't be embedded. Trying another...`);
        setTimeout(() => {
          tryAnotherWorkingSong();
        }, 400);
      },

      onStateChange: (event) => {
        if (event.data === YT.PlayerState.PLAYING) {
          const song = currentPlaylist[currentIndex];
          setStatus(`Now playing (${currentPlaylistName}): ${song.title}`);
        }

        if (event.data === YT.PlayerState.ENDED) {
          playNextSong();
        }
      }
    }
  });
};