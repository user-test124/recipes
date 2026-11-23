/* Site words in each language. The recipes stay as written. */
(function () {
  "use strict";
  var STRINGS = {
    en: {
      season: "Season", season_spring: "Spring", season_summer: "Summer", season_autumn: "Autumn", season_winter: "Winter",
      all_year: "All year", sources: "Sources", source_one: "Source",
      in_season_spring: "In season this spring", in_season_summer: "In season this summer",
      in_season_autumn: "In season this autumn", in_season_winter: "In season this winter",
      skip: "Skip to content", footer: "Written in plain markdown, cooked at home.", language: "Language",
      search_label: "Search recipes", search_ph: "Search {n} recipes or an ingredient", categories: "Categories",
      all: "All", show_all: "Show all recipes", latest: "Recently written down", all_recipes: "All recipes",
      by_tag: "By tag", empty: "No recipe matches “{q}”. Try one ingredient, like “feta” or “rice”.",
      tagged: "Tagged #{tag} ({n})", from: "From {x}", source: "Source:", also: "Also:",
      makes: "Makes", prep: "Preparation", cook: "Cooking",
      ingredients: "Ingredients", steps: "Method", tricks: "Tips", history: "The story",
      hint_ingredients: "Tap an ingredient once you have it ready.", hint_steps: "Tap a step when it’s done.",
      wake_off: "Keep screen on", wake_on: "Screen stays on", more: "More in {x}",
      nf_title: "This page isn’t in the notebook", nf_text: "The recipe may have been renamed.", nf_link: "Browse all recipes"
    },
    fr: {
      season: "Saison", season_spring: "Printemps", season_summer: "Été", season_autumn: "Automne", season_winter: "Hiver",
      all_year: "Toute l’année", sources: "Sources", source_one: "Source",
      in_season_spring: "De saison ce printemps", in_season_summer: "De saison cet été",
      in_season_autumn: "De saison cet automne", in_season_winter: "De saison cet hiver",
      skip: "Aller au contenu", footer: "Écrit en markdown, cuisiné à la maison.", language: "Langue",
      search_label: "Rechercher une recette", search_ph: "Chercher parmi {n} recettes ou un ingrédient", categories: "Catégories",
      all: "Tout", show_all: "Voir toutes les recettes", latest: "Notées récemment", all_recipes: "Toutes les recettes",
      by_tag: "Par étiquette", empty: "Aucune recette ne correspond à « {q} ». Essayez un seul ingrédient, comme « feta » ou « riz ».",
      tagged: "Étiquette #{tag} ({n})", from: "Par {x}", source: "Source :", also: "Aussi :",
      makes: "Pour", prep: "Préparation", cook: "Cuisson",
      ingredients: "Ingrédients", steps: "Étapes", tricks: "Astuces", history: "L’histoire",
      hint_ingredients: "Touchez un ingrédient quand il est prêt.", hint_steps: "Touchez une étape quand elle est faite.",
      wake_off: "Garder l’écran allumé", wake_on: "L’écran reste allumé", more: "Aussi dans {x}",
      nf_title: "Cette page n’est pas dans le carnet", nf_text: "La recette a peut-être été renommée.", nf_link: "Voir toutes les recettes"
    },
    it: {
      season: "Stagione", season_spring: "Primavera", season_summer: "Estate", season_autumn: "Autunno", season_winter: "Inverno",
      all_year: "Tutto l’anno", sources: "Fonti", source_one: "Fonte",
      in_season_spring: "Di stagione questa primavera", in_season_summer: "Di stagione questa estate",
      in_season_autumn: "Di stagione questo autunno", in_season_winter: "Di stagione questo inverno",
      skip: "Vai al contenuto", footer: "Scritto in markdown, cucinato a casa.", language: "Lingua",
      search_label: "Cerca ricette", search_ph: "Cerca tra {n} ricette o un ingrediente", categories: "Categorie",
      all: "Tutte", show_all: "Mostra tutte le ricette", latest: "Scritte di recente", all_recipes: "Tutte le ricette",
      by_tag: "Per etichetta", empty: "Nessuna ricetta corrisponde a «{q}». Prova un solo ingrediente, come «feta» o «riso».",
      tagged: "Etichetta #{tag} ({n})", from: "Di {x}", source: "Fonte:", also: "Anche:",
      makes: "Dosi", prep: "Preparazione", cook: "Cottura",
      ingredients: "Ingredienti", steps: "Procedimento", tricks: "Consigli", history: "La storia",
      hint_ingredients: "Tocca un ingrediente quando è pronto.", hint_steps: "Tocca un passaggio quando è fatto.",
      wake_off: "Tieni lo schermo acceso", wake_on: "Lo schermo resta acceso", more: "Altro in {x}",
      nf_title: "Questa pagina non è nel quaderno", nf_text: "Forse la ricetta è stata rinominata.", nf_link: "Vedi tutte le ricette"
    }
  };

  var page = {};
  try { page = JSON.parse(document.getElementById("page-i18n").textContent); } catch (e) {}
  var langs = page.languages || ["en"];
  var lang = document.documentElement.lang || langs[0];

  var t = function (key, vars) {
    var table = STRINGS[lang] || STRINGS.en;
    var s = key === "tagline" && page.tagline ? page.tagline[lang] : (table[key] || STRINGS.en[key] || "");
    return (s || "").replace(/\{(\w+)\}/g, function (_, k) { return vars && vars[k] != null ? vars[k] : ""; });
  };
  var labelOf = function (key, fallback) {
    var l = page.labels && page.labels[key];
    return (l && l[lang]) || fallback;
  };

  var translate = function () {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      if (el.dataset.en == null) el.dataset.en = el.textContent;
      var x = el.dataset.labelX ? labelOf(el.dataset.labelX, el.dataset.x) : el.dataset.x;
      el.textContent = t(el.dataset.i18n, { x: x, n: el.dataset.n }) || el.dataset.en;
    });
    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.dataset.i18nAttr.split(";").forEach(function (pair) {
        var p = pair.split(":");
        el.setAttribute(p[0], t(p[1], { n: el.dataset.n }));
      });
    });
    document.querySelectorAll("[data-label]").forEach(function (el) {
      if (el.dataset.en == null) el.dataset.en = el.textContent;
      el.textContent = labelOf(el.dataset.label, el.dataset.en);
    });
    document.querySelectorAll(".lang-switch button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
    });
    document.documentElement.classList.remove("i18n-pending");
    document.dispatchEvent(new Event("langchange"));
  };

  document.querySelectorAll(".lang-switch button").forEach(function (b) {
    b.addEventListener("click", function () {
      lang = b.dataset.lang;
      try { localStorage.setItem("lang", lang); } catch (e) {}
      translate();
    });
  });

  window.i18n = { t: t, lang: function () { return lang; } };
  translate();
})();
