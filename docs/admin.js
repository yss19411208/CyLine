(function () {
  const state = {
    maps: [],
    unknownMaps: [],
    lineups: [],
    reports: [],
    filteredLineups: [],
    selectedLineup: null
  };

  const adminStatus = document.getElementById("adminStatus");
  const adminToken = document.getElementById("adminToken");
  const adminMapFilter = document.getElementById("adminMapFilter");
  const adminKeyword = document.getElementById("adminKeyword");
  const adminReviewOnly = document.getElementById("adminReviewOnly");
  const adminList = document.getElementById("adminList");
  const adminMapTitle = document.getElementById("adminMapTitle");
  const adminMapStatus = document.getElementById("adminMapStatus");
  const adminMapStage = document.getElementById("adminMapStage");
  const adminMapImage = document.getElementById("adminMapImage");
  const adminMapPins = document.getElementById("adminMapPins");
  const adminLineupImage = document.getElementById("adminLineupImage");
  const adminImageLink = document.getElementById("adminImageLink");
  const adminImageStatus = document.getElementById("adminImageStatus");
  const adminReports = document.getElementById("adminReports");
  const adminForm = document.getElementById("adminForm");
  const adminEditMap = document.getElementById("adminEditMap");
  const adminDeleteButton = document.getElementById("adminDeleteButton");
  const adminResult = document.getElementById("adminResult");

  async function initialize() {
    await loadMaps();
    setupMapOptions();
    await loadLineups();
    await loadReports();
  }

  async function loadMaps() {
    const response = await fetch("data/maps.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`maps.json HTTP ${response.status}`);
    }
    const mapsData = await response.json();
    state.maps = Array.isArray(mapsData.maps) ? mapsData.maps : [];
  }

  async function loadLineups() {
    const response = await fetch("data/index.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`index.json HTTP ${response.status}`);
    }
    const indexData = await response.json();
    state.lineups = Array.isArray(indexData.lineups) ? indexData.lineups : [];
    updateUnknownMaps();
    setupMapOptions();
    adminStatus.textContent = `${state.lineups.length}件`;
    applyFilters();
    if (state.filteredLineups[0]) {
      selectLineup(state.filteredLineups[0].id);
    }
  }

  async function loadReports() {
    try {
      const response = await fetch("data/reports.json", { cache: "no-store" });
      if (!response.ok) {
        state.reports = [];
        renderReports();
        return;
      }
      const reportsData = await response.json();
      state.reports = Array.isArray(reportsData.reports) ? reportsData.reports : [];
    } catch (error) {
      state.reports = [];
    }
    renderReports();
  }

  function updateUnknownMaps() {
    const knownMaps = new Set(state.maps.map((mapEntry) => mapEntry.display_name));
    const unknownMaps = state.lineups
      .map((lineup) => lineup.map)
      .filter((mapName) => mapName && !knownMaps.has(mapName));
    state.unknownMaps = Array.from(new Set(unknownMaps)).sort((left, right) =>
      String(left).localeCompare(String(right), "ja")
    );
  }

  function setupMapOptions() {
    const previousFilterMap = adminMapFilter.value;
    const previousEditMap = adminEditMap.value;

    adminMapFilter.innerHTML = "";
    appendMapOption(adminMapFilter, "", "すべて");
    adminEditMap.innerHTML = "";

    state.maps.forEach((mapEntry) => {
      appendMapOption(adminMapFilter, mapEntry.display_name, mapEntry.display_name);
      appendMapOption(adminEditMap, mapEntry.display_name, mapEntry.display_name);
    });

    state.unknownMaps.forEach((mapName) => {
      const label = `${mapName}（未対応）`;
      appendMapOption(adminMapFilter, mapName, label, true);
      appendMapOption(adminEditMap, mapName, label, true);
    });

    setSelectValueIfPresent(adminMapFilter, previousFilterMap, "");
    setSelectValueIfPresent(adminEditMap, previousEditMap, state.maps[0]?.display_name || "");
  }

  function appendMapOption(selectElement, value, label, unsupported = false) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (unsupported) {
      option.dataset.unsupported = "true";
    }
    selectElement.appendChild(option);
  }

  function setSelectValueIfPresent(selectElement, preferredValue, fallbackValue) {
    const values = Array.from(selectElement.options).map((option) => option.value);
    if (values.includes(preferredValue)) {
      selectElement.value = preferredValue;
      return;
    }
    if (values.includes(fallbackValue)) {
      selectElement.value = fallbackValue;
    }
  }

  function applyFilters() {
    const selectedMap = adminMapFilter.value;
    const keyword = adminKeyword.value.trim().toLowerCase();
    const reviewOnly = adminReviewOnly.checked;
    state.filteredLineups = state.lineups.filter((lineup) => {
      const position = getPosition(lineup);
      if (selectedMap && lineup.map !== selectedMap) {
        return false;
      }
      if (reviewOnly && !position.needs_review) {
        return false;
      }
      if (keyword) {
        const searchableText = [
          lineup.id,
          lineup.title,
          lineup.description,
          lineup.map,
          lineup.ability_label,
          lineup.author?.display_name
        ].join(" ").toLowerCase();
        if (!searchableText.includes(keyword)) {
          return false;
        }
      }
      return true;
    });
    renderList();
    renderMap();
  }

  function renderList() {
    adminList.innerHTML = "";
    if (state.filteredLineups.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "定点が見つかりません。";
      adminList.appendChild(empty);
      return;
    }

    state.filteredLineups.forEach((lineup) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "admin-list-item";
      if (isUnknownMap(lineup.map)) {
        button.classList.add("unsupported-map");
      }
      if (state.selectedLineup?.id === lineup.id) {
        button.classList.add("active");
      }

      const title = document.createElement("span");
      title.textContent = lineup.title || `${formatMapName(lineup.map)} ${lineup.ability_label}`;

      const meta = document.createElement("small");
      meta.textContent = `${formatMapName(lineup.map)} / ${formatPosition(getPosition(lineup))}`;

      button.append(title, meta);
      button.addEventListener("click", () => selectLineup(lineup.id));
      adminList.appendChild(button);
    });
  }

  function selectLineup(lineupId) {
    const lineup = state.lineups.find((item) => item.id === lineupId);
    if (!lineup) {
      return;
    }
    state.selectedLineup = lineup;
    fillForm(lineup);
    renderPreview(lineup);
    renderList();
    renderMap();
  }

  function fillForm(lineup) {
    const position = getPosition(lineup);
    adminForm.elements.id.value = lineup.id;
    adminForm.elements.title.value = lineup.title || "";
    adminForm.elements.description.value = lineup.description || "";
    adminForm.elements.map.value = lineup.map;
    adminForm.elements.ability.value = lineup.ability;
    adminForm.elements.jump.checked = Boolean(lineup.jump);
    adminForm.elements.position_x.value = hasMapPoint(position) ? Number(position.x_percent).toFixed(2) : "";
    adminForm.elements.position_y.value = hasMapPoint(position) ? Number(position.y_percent).toFixed(2) : "";
    adminForm.elements.needs_review.checked = Boolean(position.needs_review);
    adminResult.textContent = "";
    adminResult.className = "form-result";
  }

  function renderPreview(lineup) {
    if (!lineup?.image_path) {
      adminLineupImage.onerror = null;
      adminLineupImage.removeAttribute("src");
      adminLineupImage.alt = "";
      adminImageLink.removeAttribute("href");
      adminImageStatus.textContent = "画像がありません。";
      return;
    }

    adminLineupImage.onerror = () => {
      adminImageStatus.textContent = `画像を読み込めません: ${lineup.image_path}`;
    };
    adminLineupImage.src = lineup.image_path;
    adminLineupImage.alt = lineup.title || `${lineup.map} ${lineup.ability_label}`;
    adminImageLink.href = lineup.image_path;
    adminImageStatus.textContent = lineup.image_path;
  }

  function renderMap() {
    const selectedMap = getSelectedMapName();
    const mapEntry = getMapEntry(selectedMap);
    adminMapTitle.textContent = selectedMap ? formatMapName(selectedMap) : "マップ";
    adminMapPins.innerHTML = "";

    if (!mapEntry) {
      adminMapImage.removeAttribute("src");
      adminMapImage.alt = "";
      adminMapImage.style.transform = "";
      adminMapStatus.textContent = selectedMap
        ? "現在のVALORANTマップ一覧にないマップです。編集欄で正しいマップへ変更してください。"
        : "マップを選択してください。";
      return;
    }

    adminMapImage.src = mapEntry.asset_path || mapEntry.source_url || "";
    adminMapImage.alt = `${selectedMap} map`;
    adminMapImage.style.transform = getMapImageTransform(mapEntry.attacker_up_transform);

    const mapLineups = state.lineups.filter((lineup) => lineup.map === selectedMap);
    adminMapStatus.textContent = `${mapLineups.length}件`;
    mapLineups.forEach((lineup, index) => {
      const position = getPosition(lineup);
      if (!hasMapPoint(position)) {
        return;
      }
      const pin = document.createElement("button");
      pin.type = "button";
      pin.className = position.needs_review ? "map-pin needs-review" : "map-pin";
      if (state.selectedLineup?.id === lineup.id) {
        pin.classList.add("active");
      }
      pin.style.left = `${position.x_percent}%`;
      pin.style.top = `${position.y_percent}%`;
      pin.textContent = String(index + 1);
      pin.addEventListener("click", (event) => {
        event.stopPropagation();
        selectLineup(lineup.id);
      });
      adminMapPins.appendChild(pin);
    });
  }

  function setFormPositionFromMap(event) {
    if (!state.selectedLineup || !getMapEntry(getSelectedMapName())) {
      return;
    }

    const rect = adminMapStage.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }

    const xPercent = clamp(((event.clientX - rect.left) / rect.width) * 100, 0, 100);
    const yPercent = clamp(((event.clientY - rect.top) / rect.height) * 100, 0, 100);
    adminForm.elements.position_x.value = xPercent.toFixed(2);
    adminForm.elements.position_y.value = yPercent.toFixed(2);
    adminForm.elements.needs_review.checked = false;

    const position = getPosition(state.selectedLineup);
    position.x_percent = Number(xPercent.toFixed(2));
    position.y_percent = Number(yPercent.toFixed(2));
    position.needs_review = false;
    renderMap();
  }

  async function submitAdminUpdate(event) {
    event.preventDefault();
    const config = window.CYLINE_CONFIG || {};
    const apiBaseUrl = (config.apiBaseUrl || "").replace(/\/$/, "");
    const token = adminToken.value.trim();
    adminResult.className = "form-result";
    adminResult.textContent = "";
    if (!apiBaseUrl) {
      showError("APIのURLが設定されていません。");
      return;
    }
    if (!token) {
      showError("管理トークンを入力してください。");
      return;
    }

    const positionX = Number(adminForm.elements.position_x.value);
    const positionY = Number(adminForm.elements.position_y.value);
    if (!Number.isFinite(positionX) || !Number.isFinite(positionY)) {
      showError("座標は数値で入力してください。");
      return;
    }

    const lineupId = adminForm.elements.id.value;
    const body = {
      title: adminForm.elements.title.value,
      description: adminForm.elements.description.value,
      map: adminForm.elements.map.value,
      ability: adminForm.elements.ability.value,
      jump: adminForm.elements.jump.checked,
      position_x: positionX,
      position_y: positionY,
      needs_review: adminForm.elements.needs_review.checked
    };

    const submitButton = adminForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      const response = await fetch(`${apiBaseUrl}/api/admin/lineups/${encodeURIComponent(lineupId)}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CyLine-Admin-Token": token
        },
        body: JSON.stringify(body)
      });
      const responseData = await response.json();
      if (!response.ok) {
        throw new Error(responseData.error || `HTTP ${response.status}`);
      }
      replaceLineup(responseData.record);
      selectLineup(responseData.record.id);
      adminResult.textContent = `更新しました: ${responseData.record.id}`;
    } catch (error) {
      showError(`更新に失敗しました: ${error.message}`);
    } finally {
      submitButton.disabled = false;
    }
  }

  async function deleteSelectedLineup() {
    if (!state.selectedLineup) {
      showError("削除する定点を選択してください。");
      return;
    }

    const config = window.CYLINE_CONFIG || {};
    const apiBaseUrl = (config.apiBaseUrl || "").replace(/\/$/, "");
    const token = adminToken.value.trim();
    adminResult.className = "form-result";
    adminResult.textContent = "";
    if (!apiBaseUrl) {
      showError("APIのURLが設定されていません。");
      return;
    }
    if (!token) {
      showError("管理トークンを入力してください。");
      return;
    }

    const lineupId = state.selectedLineup.id;
    const confirmed = window.confirm(
      `定点 ${lineupId} を削除します。画像とJSONも削除され、元に戻せません。`
    );
    if (!confirmed) {
      return;
    }

    adminDeleteButton.disabled = true;
    try {
      const response = await fetch(`${apiBaseUrl}/api/admin/lineups/${encodeURIComponent(lineupId)}`, {
        method: "DELETE",
        headers: {
          "X-CyLine-Admin-Token": token
        }
      });
      const responseData = await response.json();
      if (!response.ok) {
        throw new Error(responseData.error || `HTTP ${response.status}`);
      }

      state.lineups = state.lineups.filter((lineup) => lineup.id !== lineupId);
      state.selectedLineup = null;
      updateUnknownMaps();
      setupMapOptions();
      applyFilters();
      if (state.filteredLineups[0]) {
        selectLineup(state.filteredLineups[0].id);
      } else {
        clearSelection();
      }
      adminResult.textContent = `削除しました: ${lineupId}`;
    } catch (error) {
      showError(`削除に失敗しました: ${error.message}`);
    } finally {
      adminDeleteButton.disabled = false;
    }
  }

  function replaceLineup(record) {
    state.lineups = state.lineups.filter((lineup) => lineup.id !== record.id);
    state.lineups.push(record);
    state.lineups.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
    updateUnknownMaps();
    setupMapOptions();
    applyFilters();
  }

  function clearSelection() {
    adminForm.reset();
    adminLineupImage.removeAttribute("src");
    adminLineupImage.alt = "";
    adminImageLink.removeAttribute("href");
    adminImageStatus.textContent = "定点を選択してください。";
    adminMapPins.innerHTML = "";
  }

  function renderReports() {
    adminReports.innerHTML = "";
    if (state.reports.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty compact-empty";
      empty.textContent = "報告はありません。";
      adminReports.appendChild(empty);
      return;
    }

    state.reports.slice(0, 20).forEach((report) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "report-item";

      const title = document.createElement("span");
      title.textContent = report.reason || "報告";

      const meta = document.createElement("small");
      meta.textContent = `${report.lineup_map || "不明"} / ${report.lineup_id || "不明"}`;

      const message = document.createElement("small");
      message.textContent = report.message || "";

      button.append(title, meta, message);
      button.addEventListener("click", () => {
        const lineup = state.lineups.find((item) => item.id === report.lineup_id);
        if (lineup) {
          selectLineup(lineup.id);
        }
      });
      adminReports.appendChild(button);
    });
  }

  function showError(message) {
    adminResult.classList.add("error");
    adminResult.textContent = message;
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

  function formatMapName(mapName) {
    if (!mapName) {
      return "不明";
    }
    return isUnknownMap(mapName) ? `${mapName}（未対応）` : mapName;
  }

  function isUnknownMap(mapName) {
    if (!mapName) {
      return false;
    }
    return !state.maps.some((entry) => entry.display_name === mapName);
  }

  function getMapEntry(mapName) {
    return state.maps.find((entry) => entry.display_name === mapName);
  }

  function getSelectedMapName() {
    if (state.selectedLineup) {
      return adminForm.elements.map.value;
    }
    return adminMapFilter.value || state.maps[0]?.display_name || state.unknownMaps[0] || "";
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

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  adminMapFilter.addEventListener("change", applyFilters);
  adminKeyword.addEventListener("input", applyFilters);
  adminReviewOnly.addEventListener("change", applyFilters);
  adminEditMap.addEventListener("change", renderMap);
  adminMapStage.addEventListener("click", setFormPositionFromMap);
  adminForm.addEventListener("submit", submitAdminUpdate);
  adminDeleteButton.addEventListener("click", deleteSelectedLineup);
  initialize().catch((error) => {
    adminStatus.textContent = "読み込み失敗";
    adminList.textContent = error.message;
  });
})();
