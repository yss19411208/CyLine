(function () {
  const state = {
    maps: [],
    lineups: [],
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
  const adminForm = document.getElementById("adminForm");
  const adminEditMap = document.getElementById("adminEditMap");
  const adminResult = document.getElementById("adminResult");

  async function initialize() {
    await loadMaps();
    setupMapOptions();
    await loadLineups();
  }

  async function loadMaps() {
    const response = await fetch("data/maps.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`maps.json HTTP ${response.status}`);
    }
    const mapsData = await response.json();
    state.maps = Array.isArray(mapsData.maps) ? mapsData.maps : [];
  }

  function setupMapOptions() {
    adminMapFilter.innerHTML = '<option value="">すべて</option>';
    adminEditMap.innerHTML = "";
    state.maps.forEach((mapEntry) => {
      const mapName = mapEntry.display_name;
      const filterOption = document.createElement("option");
      filterOption.value = mapName;
      filterOption.textContent = mapName;
      adminMapFilter.appendChild(filterOption);

      const editOption = document.createElement("option");
      editOption.value = mapName;
      editOption.textContent = mapName;
      adminEditMap.appendChild(editOption);
    });
  }

  async function loadLineups() {
    const response = await fetch("data/index.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`index.json HTTP ${response.status}`);
    }
    const indexData = await response.json();
    state.lineups = Array.isArray(indexData.lineups) ? indexData.lineups : [];
    adminStatus.textContent = `${state.lineups.length}件`;
    applyFilters();
    if (state.filteredLineups[0]) {
      selectLineup(state.filteredLineups[0].id);
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
      if (state.selectedLineup?.id === lineup.id) {
        button.classList.add("active");
      }
      const title = document.createElement("span");
      title.textContent = lineup.title || `${lineup.map} ${lineup.ability_label}`;
      const meta = document.createElement("small");
      meta.textContent = `${lineup.map} / ${formatPosition(getPosition(lineup))}`;
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

  function renderMap() {
    const selectedMap = (
      state.selectedLineup
        ? adminForm.elements.map.value
        : adminMapFilter.value || state.maps[0]?.display_name || ""
    );
    const mapEntry = state.maps.find((entry) => entry.display_name === selectedMap);
    adminMapTitle.textContent = selectedMap || "マップ";
    adminMapPins.innerHTML = "";
    if (!mapEntry) {
      adminMapImage.removeAttribute("src");
      adminMapStatus.textContent = "マップを選択してください";
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
    if (!state.selectedLineup) {
      return;
    }
    const rect = adminMapStage.getBoundingClientRect();
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

    const lineupId = adminForm.elements.id.value;
    const body = {
      title: adminForm.elements.title.value,
      description: adminForm.elements.description.value,
      map: adminForm.elements.map.value,
      ability: adminForm.elements.ability.value,
      jump: adminForm.elements.jump.checked,
      position_x: Number(adminForm.elements.position_x.value),
      position_y: Number(adminForm.elements.position_y.value),
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

  function replaceLineup(record) {
    state.lineups = state.lineups.filter((lineup) => lineup.id !== record.id);
    state.lineups.push(record);
    state.lineups.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
    applyFilters();
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
  initialize().catch((error) => {
    adminStatus.textContent = "読み込み失敗";
    adminList.textContent = error.message;
  });
})();
