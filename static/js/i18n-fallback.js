/*
 * Guarantee that `gettext` and `interpolate` exist (FR-011).
 *
 * Django's translation catalog defines both. This file runs immediately after it and defines
 * them only if it did not — a catalog that failed to load leaves an English label, which is a
 * degraded product; an undefined function leaves a broken one, and the difference matters on
 * a status pill somebody is reading to decide whether they are taking conversations.
 *
 * This replaced a `gettextOrFallback` helper that did the same job in the calling code. The
 * helper was correct and invisible to the extractor: `xgettext` recognises `gettext(...)` and
 * not a local wrapper around it, so the strings were never extracted, the catalog never
 * contained them, and every call took the fallback. Keeping the real name is what makes the
 * strings findable.
 */
window.gettext = window.gettext || function (text) {
  return text;
};

window.interpolate = window.interpolate || function (template, values) {
  return template.replace("%s", values[0]);
};
