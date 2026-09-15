(function () {
  "use strict";

  var D = window.TRACKER_DATA;
  var control = D.control;
  var alternatives = D.platforms.filter(function (p) { return p !== control; });
  var MAX = 3;

  var picksEl = document.getElementById("picks");
  var addEl = document.getElementById("add-platform");
  var diffEl = document.getElementById("diff-only");
  var searchEl = document.getElementById("search");
  var countEl = document.getElementById("count");
  var sectionsEl = document.getElementById("sections");
  var contentsEl = document.getElementById("contents-list");
  document.getElementById("as-of").textContent = D.asOf;

  var selected = [];

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Escape, then turn bare URLs into links.
  function fmt(s) {
    if (s === "") return "";
    return esc(s).replace(/https?:\/\/[^\s<>"'()]+[^\s<>"'().,;:]/g, function (url) {
      return '<a href="' + url + '" rel="noopener">' + url + "</a>";
    });
  }

  function slug(s) {
    return s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function norm(s) {
    return String(s).trim().toLowerCase();
  }

  // "Harmony/Fermi" in a source row should count as Harmony.
  function platformMatches(cell, name) {
    var c = norm(cell), n = norm(name);
    if (c === n) return true;
    return c.split("/").some(function (part) { return part.trim() === n; });
  }

  function renderContents() {
    var html = "";
    D.groups.forEach(function (g) {
      html += "<h3>" + esc(g.name) + "</h3><ul>";
      g.sheets.forEach(function (name) {
        html += '<li><a href="#' + slug(name) + '">' + esc(name) + "</a></li>";
      });
      html += "</ul>";
    });
    contentsEl.innerHTML = html;
  }

  function renderMatrix(sheet, ci, sis, names) {
    var html = '<div class="scroll"><table class="compare" data-platforms="' + names.length +
      '"><thead><tr><th scope="col">Attribute</th><th scope="col">' + esc(control) + "</th>";
    names.forEach(function (n) { html += '<th scope="col">' + esc(n) + "</th>"; });
    html += "</tr></thead><tbody>";
    sheet.rows.forEach(function (row) {
      if (row.section !== undefined) {
        html += '<tr class="section"><th colspan="' + (names.length + 2) + '">' + esc(row.section) + "</th></tr>";
        return;
      }
      var a = row.values[ci];
      var same = sis.every(function (i) { return norm(row.values[i]) === norm(a); });
      html += "<tr" + (same ? " data-same" : "") + '><th scope="row">' + esc(row.label) + "</th><td>" + fmt(a) + "</td>";
      sis.forEach(function (i) { html += "<td>" + fmt(row.values[i]) + "</td>"; });
      html += "</tr>";
    });
    return html + "</tbody></table></div>";
  }

  function renderRecords(sheet, names, filter) {
    var cols = sheet.columns;
    var html = '<div class="scroll"><table class="records"><thead><tr>';
    cols.forEach(function (c) { html += '<th scope="col">' + esc(c) + "</th>"; });
    html += "</tr></thead><tbody>";
    var order = filter ? [control].concat(names) : [null];
    order.forEach(function (who) {
      var shown = 0;
      sheet.rows.forEach(function (r) {
        if (who !== null && !platformMatches(r[0], who)) return;
        shown++;
        html += "<tr>";
        r.forEach(function (v, i) {
          var wide = v.length > 60 ? ' class="wide"' : "";
          html += i === 0 ? '<th scope="row">' + esc(v) + "</th>" : "<td" + wide + ">" + fmt(v) + "</td>";
        });
        html += "</tr>";
      });
      if (who !== null && shown === 0) {
        html += '<tr><td class="empty" colspan="' + cols.length + '">No entries for ' + esc(who) + ".</td></tr>";
      }
    });
    return html + "</tbody></table></div>";
  }

  function renderGlossary(sheet) {
    var html = '<table class="records"><thead><tr>';
    sheet.columns.forEach(function (c) { html += '<th scope="col">' + esc(c) + "</th>"; });
    html += "</tr></thead><tbody>";
    sheet.rows.forEach(function (r) {
      html += '<tr><th scope="row">' + esc(r[0]) + "</th><td>" + fmt(r[1]) + "</td><td>" + fmt(r[2]) + "</td></tr>";
    });
    return html + "</tbody></table>";
  }

  function render() {
    var ci = D.platforms.indexOf(control);
    var sis = selected.map(function (n) { return D.platforms.indexOf(n); });
    var html = "";
    D.groups.forEach(function (g) {
      html += '<h2 class="group">' + esc(g.name) + "</h2>";
      g.sheets.forEach(function (name) {
        var sheet = D.sheets[name];
        html += '<section class="sheet" id="' + slug(name) + '">';
        html += "<h3>" + esc(name) + ' <a class="top" href="#contents">contents</a></h3>';
        if (sheet.purpose) html += '<p class="purpose">' + esc(sheet.purpose) + "</p>";
        if (sheet.kind === "matrix") html += renderMatrix(sheet, ci, sis, selected);
        else if (sheet.kind === "records") html += renderRecords(sheet, selected, true);
        else if (sheet.kind === "table") html += renderRecords(sheet, selected, false);
        else if (sheet.kind === "glossary") html += renderGlossary(sheet);
        html += "</section>";
      });
    });
    sectionsEl.innerHTML = html;
    applyFilters();
  }

  function applyFilters() {
    var diffOnly = diffEl.checked;
    var q = norm(searchEl.value);
    var total = 0, shown = 0;

    var sections = sectionsEl.querySelectorAll("section.sheet");
    Array.prototype.forEach.call(sections, function (section) {
      var visibleInSheet = 0;
      var rows = section.querySelectorAll("tbody tr");
      var currentSection = null, sectionHasRows = false;

      Array.prototype.forEach.call(rows, function (tr) {
        if (tr.classList.contains("section")) {
          if (currentSection) currentSection.classList.toggle("hidden", !sectionHasRows);
          currentSection = tr;
          sectionHasRows = false;
          return;
        }
        total++;
        var hide = false;
        if (diffOnly && tr.hasAttribute("data-same")) hide = true;
        if (!hide && q && norm(tr.textContent).indexOf(q) === -1) hide = true;
        tr.classList.toggle("hidden", hide);
        if (!hide) { shown++; visibleInSheet++; sectionHasRows = true; }
      });
      if (currentSection) currentSection.classList.toggle("hidden", !sectionHasRows);
      section.classList.toggle("hidden", visibleInSheet === 0);
    });

    // Hide a group heading when every sheet under it is hidden.
    var groups = sectionsEl.querySelectorAll("h2.group");
    Array.prototype.forEach.call(groups, function (h2) {
      var el = h2.nextElementSibling, any = false;
      while (el && el.tagName !== "H2") {
        if (!el.classList.contains("hidden")) any = true;
        el = el.nextElementSibling;
      }
      h2.classList.toggle("hidden", !any);
    });

    countEl.textContent = (diffOnly || q) ? shown + " of " + total + " rows" : total + " rows";
  }

  // One dropdown per chosen platform, plus a remove link once there is more than one.
  function renderPicks() {
    picksEl.innerHTML = "";
    selected.forEach(function (name, idx) {
      var wrap = document.createElement("span");
      wrap.className = "pick";

      var sel = document.createElement("select");
      sel.setAttribute("aria-label", "Platform " + (idx + 1));
      alternatives.forEach(function (p) {
        var opt = document.createElement("option");
        opt.value = p;
        opt.textContent = p;
        if (p !== name && selected.indexOf(p) !== -1) opt.disabled = true;
        sel.appendChild(opt);
      });
      sel.value = name;
      sel.addEventListener("change", function () {
        selected[idx] = sel.value;
        update();
      });
      wrap.appendChild(sel);

      if (selected.length > 1) {
        var rm = document.createElement("button");
        rm.type = "button";
        rm.className = "remove";
        rm.textContent = "remove";
        rm.setAttribute("aria-label", "Remove " + name);
        rm.addEventListener("click", function () {
          selected.splice(idx, 1);
          update();
        });
        wrap.appendChild(rm);
      }
      picksEl.appendChild(wrap);
    });
    addEl.hidden = selected.length >= MAX;
  }

  function nextUnused() {
    for (var i = 0; i < alternatives.length; i++) {
      if (selected.indexOf(alternatives[i]) === -1) return alternatives[i];
    }
    return null;
  }

  function fromUrl() {
    var list = [];
    var m = /[?&]compare=([^&]+)/.exec(location.search);
    if (m) {
      list = decodeURIComponent(m[1].replace(/\+/g, " ")).split(",");
    } else {
      var p = /[?&]platform=([^&]+)/.exec(location.search);
      if (p) list = [decodeURIComponent(p[1].replace(/\+/g, " "))];
    }
    var out = [];
    list.forEach(function (n) {
      n = n.trim();
      if (alternatives.indexOf(n) !== -1 && out.indexOf(n) === -1 && out.length < MAX) out.push(n);
    });
    return out.length ? out : [alternatives[0]];
  }

  function setUrl() {
    var url = location.pathname + "?compare=" + selected.map(encodeURIComponent).join(",") + location.hash;
    try { history.replaceState(null, "", url); } catch (e) { /* not allowed in some embeds */ }
  }

  function update() {
    setUrl();
    renderPicks();
    render();
  }

  addEl.addEventListener("click", function () {
    var p = nextUnused();
    if (selected.length >= MAX || !p) return;
    selected.push(p);
    update();
    var sels = picksEl.querySelectorAll("select");
    sels[sels.length - 1].focus();
  });

  renderContents();
  selected = fromUrl();
  renderPicks();
  render();
  diffEl.addEventListener("change", applyFilters);
  searchEl.addEventListener("input", applyFilters);
})();
