(function () {
  const fallbackMaps = [
    "Abyss",
    "Ascent",
    "Bind",
    "Breeze",
    "Corrode",
    "District",
    "Drift",
    "Fracture",
    "Glitch",
    "Haven",
    "Icebox",
    "Kasbah",
    "Lotus",
    "Pearl",
    "Piazza",
    "Split",
    "Summit",
    "Sunset"
  ];

  const state = {
    maps: [],
    lineups: [],
    filteredLineups: []
  };

  const statusText = document.getElementById("statusText");
  const mapFilter = document.getElementById("mapFilter");
  const abilityFilter = document.getElementById("abilityFilter");
  const jumpFilter = document.getElementById("jumpFilter");
  const registerMap = document.getElementById("registerMap");
  const lineupGrid = document.getElementById("lineupGrid");
  const registerForm = document.getElementById("registerForm");
  const formResult = document.getElementById("formResult");
  const detailDialog = document.getElementById("detailDialog");
  const detailImage = document.getElementById("detailImage");
  const detailTitle = document.getElementById("detailTitle");
  const detailMeta = document.getElementById("detailMeta");
  const detailDescription = document.getElementById("detailDescription");
  const closeDialog = document.getElementById("closeDialog");
  const mapTitle = document.getElementById("mapTitle");
  const mapStatus = document.getElementById("mapStatus");
  const mapImage = document.getElementById("mapImage");
  const mapPins = document.getElementById("mapPins");

  async function initialize() {
    await loadMaps();
    setupMapOptions();
    await loadLineups();
  }

  async function loadMaps() {
    try {
      const response = await fetch("data/maps.json", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const mapsData = await response.json();
      state.maps = Array.isArray(mapsData.maps) ? mapsData.maps : [];
    } catch (error) {
      state.maps = fallbackMaps.map((mapName) => ({
        display_name: mapName,
        asset_path: "",
        source_url: ""
      }));
    }
  }

  function setupMapOptions() {
    mapFilter.innerHTML = '<option value="">すべて</option>';
    registerMap.innerHTML = "";
    state.maps.forEach((mapEntry) => {
      const mapName = mapEntry.display_name;
      const filterOption = document.createElement("option");
      filterOption.value = mapName;
      filterOption.textContent = mapName;
      mapFilter.appendChild(filterOption);

      const registerOption = document.createElement("option");
      registerOption.value = mapName;
      registerOption.textContent = mapName;
      registerMap.appendChild(registerOption);
    });
  }

  async function loadLineups() {
    try {
      const response = await fetch("data/index.json", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const indexData = await response.json();
      state.lineups = Array.isArray(indexData.lineups) ? indexData.lineups : [];
      applyFilters();
      statusText.textContent = `${state.lineups.length}件`;
    } catch (error) {
      statusText.textContent = "読み込み失敗";
      lineupGrid.innerHTML = '<p class="empty">data/index.jsonを読み込めませんでした。</p>';
    }
  }

  function applyFilters() {
    const selectedMap = mapFilter.value;
    const selectedAbility = abilityFilter.value;
    const jumpOnly = jumpFilter.checked;

    state.filteredLineups = state.lineups.filter((lineup) => {
      if (selectedMap && lineup.map !== selectedMap) {
        return false;
      }

      if (selectedAbility && lineup.ability !== selectedAbility) {
        return false;
      }

      if (jumpOnly && !lineup.jump) {
        return false;
      }

      return true;
    });

    renderMap();
    renderLineups();
  }

  function renderMap() {
    const selectedMap = mapFilter.value || state.filteredLineups[0]?.map || state.maps[0]?.display_name || "";
    const mapEntry = state.maps.find((entry) => entry.display_name === selectedMap);
    mapTitle.textContent = selectedMap || "マップ";
    mapPins.innerHTML = "";

    if (!mapEntry) {
      mapImage.removeAttribute("src");
      mapImage.style.transform = "";
      mapStatus.textContent = "マップを選択してください";
      return;
    }

    setMapImageSource(mapEntry, selectedMap);
    const mapLineups = state.filteredLineups.filter((lineup) => lineup.map === selectedMap);
    mapStatus.textContent = `${mapLineups.length}件`;

    mapLineups.forEach((lineup, index) => {
      const position = getPosition(lineup);
      if (!hasMapPoint(position)) {
        return;
      }

      const pin = document.createElement("button");
      pin.type = "button";
      pin.className = position.needs_review ? "map-pin needs-review" : "map-pin";
      pin.style.left = `${position.x_percent}%`;
      pin.style.top = `${position.y_percent}%`;
      pin.textContent = String(index + 1);
      pin.title = lineup.title || `${lineup.map} ${lineup.ability_label}`;
      pin.addEventListener("click", () => openDetail(lineup));
      mapPins.appendChild(pin);
    });
  }

  function setMapImageSource(mapEntry, selectedMap) {
    const localAssetPath = mapEntry.asset_path || "";
    const remoteSourceUrl = mapEntry.source_url || "";
    mapImage.style.transform = getMapImageTransform(mapEntry.attacker_up_transform);

    mapImage.onerror = null;
    if (!localAssetPath && !remoteSourceUrl) {
      mapImage.removeAttribute("src");
      mapImage.alt = `${selectedMap} map`;
      return;
    }

    if (localAssetPath && remoteSourceUrl && localAssetPath !== remoteSourceUrl) {
      mapImage.onerror = () => {
        mapImage.onerror = null;
        mapImage.src = remoteSourceUrl;
      };
    }

    mapImage.src = localAssetPath || remoteSourceUrl;
    mapImage.alt = `${selectedMap} map`;
  }

  function getMapImageTransform(attackerUpTransform) {
    if (attackerUpTransform === "rotate_clockwise_90") {
      return "rotate(90deg)";
    }
    if (attackerUpTransform === "rotate_counterclockwise_90") {
      return "rotate(270deg)";
    }
    if (attackerUpTransform === "rotate_180") {
      return "rotate(180deg)";
    }
    if (attackerUpTransform === "flip_horizontal") {
      return "scaleX(-1)";
    }
    if (attackerUpTransform === "flip_vertical") {
      return "scaleY(-1)";
    }
    return "";
  }

  function renderLineups() {
    lineupGrid.innerHTML = "";

    if (state.filteredLineups.length === 0) {
      lineupGrid.innerHTML = '<p class="empty">定点が見つかりません。</p>';
      return;
    }

    state.filteredLineups.forEach((lineup) => {
      const card = document.createElement("article");
      card.className = "lineup-card";
      card.tabIndex = 0;
      card.addEventListener("click", () => openDetail(lineup));
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDetail(lineup);
        }
      });

      const image = document.createElement("img");
      image.src = lineup.image_path;
      image.alt = lineup.title || `${lineup.map} ${lineup.ability_label}`;

      const body = document.createElement("div");
      body.className = "card-body";

      const title = document.createElement("div");
      title.className = "card-title";
      title.textContent = lineup.title || `${lineup.map} ${lineup.ability_label}`;

      const meta = document.createElement("div");
      meta.className = "card-meta";
      [lineup.map, lineup.ability_label, lineup.jump_label, formatPosition(getPosition(lineup))].forEach((label) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = label;
        meta.appendChild(chip);
      });

      body.append(title, meta);
      card.append(image, body);
      lineupGrid.appendChild(card);
    });
  }

  function openDetail(lineup) {
    detailImage.src = lineup.image_path;
    detailImage.alt = lineup.title || `${lineup.map} ${lineup.ability_label}`;
    detailTitle.textContent = lineup.title || `${lineup.map} ${lineup.ability_label}`;
    detailDescription.textContent = lineup.description || "";
    detailMeta.innerHTML = "";

    const position = getPosition(lineup);
    const fields = [
      ["マップ", lineup.map],
      ["アビリティ", lineup.ability_label],
      ["ジャンプ", lineup.jump_label],
      ["座標", formatPosition(position)],
      ["信頼度", String(position.confidence ?? "不明")],
      ["登録者", lineup.author?.display_name || "不明"],
      ["登録日時", lineup.created_at]
    ];

    fields.forEach(([label, value]) => {
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = value || "";
      detailMeta.append(term, detail);
    });

    detailDialog.showModal();
  }

  function getPosition(lineup) {
    if (lineup.map_position) {
      return lineup.map_position;
    }

    if (lineup.detected_position) {
      return lineup.detected_position;
    }

    return {};
  }

  function hasMapPoint(position) {
    return typeof position.x_percent === "number" && typeof position.y_percent === "number";
  }

  function formatPosition(position) {
    if (!hasMapPoint(position)) {
      return "要確認";
    }
    const reviewSuffix = position.needs_review ? " / 要確認" : "";
    return `${Number(position.x_percent).toFixed(2)}, ${Number(position.y_percent).toFixed(2)}${reviewSuffix}`;
  }

  async function submitRegistration(event) {
    event.preventDefault();
    formResult.className = "form-result";
    formResult.textContent = "";

    const config = window.CYLINE_CONFIG || {};
    if (!config.apiBaseUrl) {
      formResult.classList.add("error");
      formResult.textContent = "APIのURLが設定されていません。";
      return;
    }

    const formData = new FormData(registerForm);
    formData.set("jump", registerForm.elements.jump.checked ? "true" : "false");
    const submitButton = registerForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;

    try {
      const response = await fetch(`${config.apiBaseUrl.replace(/\/$/, "")}/api/lineups`, {
        method: "POST",
        body: formData
      });
      const responseData = await response.json();
      if (!response.ok) {
        throw new Error(responseData.error || `HTTP ${response.status}`);
      }

      formResult.textContent = `登録しました: ${responseData.record.id}`;
      registerForm.reset();
      await loadLineups();
    } catch (error) {
      formResult.classList.add("error");
      formResult.textContent = buildRegistrationErrorMessage(error, config.apiBaseUrl);
    } finally {
      submitButton.disabled = false;
    }
  }

  function buildRegistrationErrorMessage(error, apiBaseUrl) {
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      return `登録に失敗しました: APIに接続できません。cyline-apiが起動しているか、API URL (${apiBaseUrl}) が正しいか確認してください。`;
    }

    return `登録に失敗しました: ${error.message}`;
  }

  mapFilter.addEventListener("change", applyFilters);
  abilityFilter.addEventListener("change", applyFilters);
  jumpFilter.addEventListener("change", applyFilters);
  registerForm.addEventListener("submit", submitRegistration);
  closeDialog.addEventListener("click", () => detailDialog.close());
  initialize();
})();
