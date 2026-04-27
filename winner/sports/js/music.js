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
  { title: "choosin texas", videoId: "4hpduPieV7A" },
];

const testVideos = [
  { title: "Arctic Monkeys - Do I Wanna Know? (Working)", videoId: "F586JktJyEg" },
];

// Use either a playlist ID or full Spotify playlist URL.
const spotifyPlaylists = [
  {
    title: "Tate McRae",
    playlistId: "1kcGTH36NymIBMadgxbL2v"
  },
  {
    title: "Noah Kahan",
    playlistId: "6EVaH9p1mmMSFBJdVgoLyq"
  },
  {
    title: "treaty oak revival",
    playlistId: "6I3Ew5hkJgguxfD7RGYVoY"
  }
];

let player = null;
let currentPlaylist = treatyOakVideos;
let currentPlaylistName = "Treaty Oak Revival";
let currentIndex = 0;
let triedIndexes = new Set();

let currentSpotifyPlaylistIndex = 0;

function setStatus(text) {
  const el = document.getElementById("music-status");
  if (el) el.textContent = text;
}

function setSpotifyStatus(text) {
  const el = document.getElementById("spotify-status");
  if (el) el.textContent = text;
}

function getRandomIndex(length) {
  return Math.floor(Math.random() * length);
}

function getAnotherIndex(excludeIndex, length) {
  if (length <= 1) return excludeIndex;

  let index;
  do {
    index = getRandomIndex(length);
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

function populateSpotifyPlaylistDropdown() {
  const select = document.getElementById("spotify-playlist-select");
  if (!select) return;

  select.innerHTML = '<option value="">Choose a playlist</option>';

  spotifyPlaylists.forEach((playlist, index) => {
    const option = document.createElement("option");
    option.value = index;
    option.textContent = playlist.title;
    select.appendChild(option);
  });
}

function normalizeSpotifyPlaylistId(value) {
  if (!value) return "";

  if (!value.includes("spotify")) {
    return value.trim();
  }

  const match = value.match(/playlist\/([a-zA-Z0-9]+)/);
  return match ? match[1] : "";
}

function loadSpotifyPlaylist(index) {
  if (index < 0 || index >= spotifyPlaylists.length) return;

  currentSpotifyPlaylistIndex = index;

  const playlist = spotifyPlaylists[index];
  const playlistId = normalizeSpotifyPlaylistId(playlist.playlistId);

  if (!playlistId || playlistId.startsWith("PUT_YOUR_")) {
    setSpotifyStatus(`Set a real Spotify playlist ID for: ${playlist.title}`);
    return;
  }

  const embed = document.getElementById("spotify-embed");
  if (!embed) return;

  embed.innerHTML = `
    <iframe
      style="border-radius:12px"
      src="https://open.spotify.com/embed/playlist/${playlistId}"
      width="100%"
      height="380"
      frameborder="0"
      allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture">
    </iframe>
  `;

  setSpotifyStatus(`Loaded playlist: ${playlist.title}`);
}

function loadSelectedSpotifyPlaylist() {
  const select = document.getElementById("spotify-playlist-select");
  if (!select || select.value === "") {
    setSpotifyStatus("Choose a Spotify playlist first.");
    return;
  }

  loadSpotifyPlaylist(Number(select.value));
}

function playRandomSpotifyPlaylist() {
  if (!spotifyPlaylists.length) return;

  const index = getRandomIndex(spotifyPlaylists.length);
  loadSpotifyPlaylist(index);

  const select = document.getElementById("spotify-playlist-select");
  if (select) {
    select.value = String(index);
  }
}

function playNextSpotifyPlaylist() {
  if (!spotifyPlaylists.length) return;

  let next = currentSpotifyPlaylistIndex + 1;
  if (next >= spotifyPlaylists.length) {
    next = 0;
  }

  loadSpotifyPlaylist(next);

  const select = document.getElementById("spotify-playlist-select");
  if (select) {
    select.value = String(next);
  }
}

function tryPlayIndex(index) {
  if (!player) return;
  if (index < 0 || index >= currentPlaylist.length) return;

  currentIndex = index;
  triedIndexes.add(index);

  const song = currentPlaylist[index];
  setStatus(`Trying (${currentPlaylistName}): ${song.title}`);
  player.loadVideoById(song.videoId);
}

function playRandomSong() {
  if (!player || !currentPlaylist.length) return;
  resetTried();
  tryPlayIndex(getRandomIndex(currentPlaylist.length));
}

function playNextSong() {
  if (!player || !currentPlaylist.length) return;
  resetTried();
  tryPlayIndex(getAnotherIndex(currentIndex, currentPlaylist.length));
}

function tryAnotherWorkingSong() {
  if (!player || !currentPlaylist.length) return;

  if (triedIndexes.size >= currentPlaylist.length) {
    setStatus(`No embeddable songs found in ${currentPlaylistName}`);
    return;
  }

  let nextIndex = getRandomIndex(currentPlaylist.length);
  while (triedIndexes.has(nextIndex)) {
    nextIndex = getRandomIndex(currentPlaylist.length);
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

window.scanPlaylist = function scanPlaylist(which = "test") {
  const playlist = which === "treaty" ? treatyOakVideos : testVideos;
  const label = which === "treaty" ? "Treaty Oak Revival" : "Test Playlist";

  switchToPlaylist(playlist, label);

  let i = 0;
  const results = [];

  function next() {
    if (i >= playlist.length) {
      console.log("SCAN_RESULTS_START");
      console.log(JSON.stringify(results, null, 2));
      console.log("SCAN_RESULTS_END");
      console.table(results);
      setStatus(`Finished scanning ${label}. Check console.`);
      return;
    }

    const song = playlist[i];
    currentIndex = i;

    let done = false;
    const timeout = setTimeout(() => {
      if (done) return;
      done = true;

      results.push({
        title: song.title,
        videoId: song.videoId,
        result: "timeout"
      });

      i += 1;
      next();
    }, 7000);

    window.__scanOnState = (event) => {
      if (done) return;
      if (event.data === YT.PlayerState.PLAYING) {
        done = true;
        clearTimeout(timeout);

        results.push({
          title: song.title,
          videoId: song.videoId,
          result: "works"
        });

        i += 1;
        setTimeout(next, 800);
      }
    };

    window.__scanOnError = (event) => {
      if (done) return;
      done = true;
      clearTimeout(timeout);

      results.push({
        title: song.title,
        videoId: song.videoId,
        result: `error ${event.data}`
      });

      i += 1;
      setTimeout(next, 800);
    };

    tryPlayIndex(i);
  }

  next();
};

window.onYouTubeIframeAPIReady = function () {
  player = new YT.Player("yt-player", {
    width: "320",
    height: "200",
    videoId: treatyOakVideos[0].videoId,
    host: "https://www.youtube-nocookie.com",
    playerVars: {
      autoplay: 0,
      rel: 0,
      playsinline: 1,
      origin: window.location.origin
    },
    events: {
      onReady: () => {
        populateDropdown("treaty-select", treatyOakVideos);
        populateDropdown("cash-select", testVideos);
        populateSpotifyPlaylistDropdown();

        setStatus(`Ready to play (${window.location.origin})`);
        setSpotifyStatus("Spotify ready");

        const nextBtn = document.getElementById("music-next");
        const treatyBtn = document.getElementById("music-play-treaty");
        const testBtn = document.getElementById("music-play-cash");
        const treatySelectedBtn = document.getElementById("music-play-treaty-selected");
        const testSelectedBtn = document.getElementById("music-play-cash-selected");

        const spotifyLoadBtn = document.getElementById("spotify-load-playlist");
        const spotifyRandomBtn = document.getElementById("spotify-random-playlist");
        const spotifyNextBtn = document.getElementById("spotify-next-playlist");

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

        if (spotifyLoadBtn) {
          spotifyLoadBtn.addEventListener("click", loadSelectedSpotifyPlaylist);
        }

        if (spotifyRandomBtn) {
          spotifyRandomBtn.addEventListener("click", playRandomSpotifyPlaylist);
        }

        if (spotifyNextBtn) {
          spotifyNextBtn.addEventListener("click", playNextSpotifyPlaylist);
        }

        if (spotifyPlaylists.length) {
          const select = document.getElementById("spotify-playlist-select");
          if (select) {
            select.value = "0";
          }
          loadSpotifyPlaylist(0);
        }
      },

      onError: (event) => {
        const badSong = currentPlaylist[currentIndex];
        console.error("YouTube error code:", event.data);
        console.error("Failed song:", badSong);
        console.error("Playlist:", currentPlaylistName);
        console.error("Origin:", window.location.origin);

        if (window.__scanOnError) {
          window.__scanOnError(event);
          return;
        }

        setStatus(`"${badSong?.title || "Unknown song"}" can't be embedded. Trying another...`);

        setTimeout(() => {
          tryAnotherWorkingSong();
        }, 400);
      },

      onStateChange: (event) => {
        if (window.__scanOnState) {
          window.__scanOnState(event);
        }

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