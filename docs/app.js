(function () {
  const maps = [
    "Abyss",
    "Ascent",
    "Bind",
    "Breeze",
    "Corrode",
    "Fracture",
    "Haven",
    "Icebox",
    "Lotus",
    "Pearl",
    "Split",
    "Sunset"
  ];

  const state = {
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

  function setupMapOptions() {
    mapFilter.innerHTML = '<option value="">すべて</option>';
    registerMap.innerHTML = "";
    maps.forEach((mapName) => {
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

    renderLineups();
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
      [lineup.map, lineup.ability_label, lineup.jump_label].forEach((label) => {
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

    const position = lineup.detected_position || {};
    const fields = [
      ["マップ", lineup.map],
      ["アビリティ", lineup.ability_label],
      ["ジャンプ", lineup.jump_label],
      ["位置", formatPosition(position)],
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

  function formatPosition(position) {
    if (typeof position.x_percent !== "number" || typeof position.y_percent !== "number") {
      return "要確認";
    }
    const reviewSuffix = position.needs_review ? " / 要確認" : "";
    return `${position.x_percent}, ${position.y_percent}${reviewSuffix}`;
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
      formResult.textContent = `登録に失敗しました: ${error.message}`;
    } finally {
      submitButton.disabled = false;
    }
  }

  setupMapOptions();
  mapFilter.addEventListener("change", applyFilters);
  abilityFilter.addEventListener("change", applyFilters);
  jumpFilter.addEventListener("change", applyFilters);
  registerForm.addEventListener("submit", submitRegistration);
  closeDialog.addEventListener("click", () => detailDialog.close());
  loadLineups();
})();
