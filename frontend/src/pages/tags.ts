import {
  addVocabularyTag,
  approveCandidate,
  getTagWeights,
  getVocabulary,
  getVocabularyCandidates,
  mergeVocabularyTags,
  rejectCandidate,
  removeVocabularyTag,
  resetTagWeight,
} from "../api";
import type { CandidateTag, TagWeight, VocabularyTag } from "../types";
import { el } from "../utils";
import { showToast } from "../components/toast";

const ICON_X = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
const ICON_CHECK = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
const ICON_MERGE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/></svg>`;
const ICON_RESET = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>`;

const DEFAULT_TAG_SHOW = 20;

export function TagsPage(): HTMLElement {
  const page = el("div", { class: "page page-tags" });
  page.appendChild(el("h1", {}, "Tag Vocabulary"));

  const content = el("div", { class: "tags-content" });
  page.appendChild(content);

  load(content);
  return page;
}

function load(container: HTMLElement): void {
  Promise.all([getVocabulary(), getVocabularyCandidates(), getTagWeights()]).then(
    ([vocab, candidates, weights]) => {
      container.innerHTML = "";
      container.appendChild(renderIntro());
      if (candidates.length > 0) {
        container.appendChild(renderCandidates(candidates, container));
      }
      container.appendChild(renderVocabulary(vocab, container));
      if (vocab.length >= 2) {
        container.appendChild(renderMerge(vocab, container));
      }
      container.appendChild(renderTagWeights(weights, container));
    }
  );
}

function renderIntro(): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "These are the tags the AI uses when scoring articles. "
        + "New tags are auto-promoted after appearing in 3+ articles. "
        + "You can also add, remove, or merge tags manually."
    )
  );
  return section;
}

function renderCandidates(
  candidates: CandidateTag[],
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  const candidateH2 = el("h2", {}, "Suggested New Tags ");
  candidateH2.appendChild(el("span", { class: "section-count" }, String(candidates.length)));
  section.appendChild(candidateH2);
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "The AI suggested these tags for recent articles. "
        + "Approve to add them to the vocabulary, or reject to discard."
    )
  );

  const list = el("div", { class: "vocab-candidate-list" });
  for (const c of candidates) {
    const row = el("div", { class: "vocab-candidate-row" });
    row.appendChild(el("span", { class: "vocab-candidate-name" }, c.name));
    const countPill = el(
      "span",
      { class: "section-count" },
      `${c.occurrences} article${c.occurrences !== 1 ? "s" : ""}`
    );
    row.appendChild(countPill);
    const approveBtn = el("button", {
      class: "btn-icon btn-approve",
      title: "Approve",
    });
    approveBtn.innerHTML = ICON_CHECK;
    approveBtn.addEventListener("click", async () => {
      try {
        await approveCandidate(c.id);
        showToast(`Approved "${c.name}"`, "success");
        load(container);
      } catch {
        showToast("Failed to approve tag", "error");
      }
    });
    const rejectBtn = el("button", {
      class: "btn-icon btn-reject",
      title: "Reject",
    });
    rejectBtn.innerHTML = ICON_X;
    rejectBtn.addEventListener("click", async () => {
      try {
        await rejectCandidate(c.id);
        showToast(`Rejected "${c.name}"`, "success");
        load(container);
      } catch {
        showToast("Failed to reject tag", "error");
      }
    });
    row.appendChild(approveBtn);
    row.appendChild(rejectBtn);
    list.appendChild(row);
  }
  section.appendChild(list);
  return section;
}

function renderVocabulary(
  vocab: VocabularyTag[],
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  const vocabH2 = el("h2", {}, "Approved Tags ");
  vocabH2.appendChild(el("span", { class: "section-count" }, String(vocab.length)));
  section.appendChild(vocabH2);

  if (vocab.length === 0) {
    section.appendChild(
      el(
        "p",
        { class: "prefs-empty" },
        "No approved tags yet. Tags used in 3+ articles are auto-approved, "
          + "or you can add them manually below."
      )
    );
  } else {
    const pillsContainer = el("div", { class: "vocab-pills" });
    for (const tag of vocab) {
      const pill = el("span", { class: "vocab-pill" });
      pill.appendChild(document.createTextNode(tag.name));
      const countBadge = el(
        "span",
        { class: "vocab-pill-count" },
        String(tag.article_count)
      );
      pill.appendChild(countBadge);
      const removeBtn = el("button", {
        class: "vocab-pill-x",
        title: "Remove from vocabulary",
      });
      removeBtn.innerHTML = ICON_X;
      removeBtn.addEventListener("click", async () => {
        try {
          await removeVocabularyTag(tag.id);
          showToast(`Removed "${tag.name}"`, "success");
          load(container);
        } catch {
          showToast("Failed to remove tag", "error");
        }
      });
      pill.appendChild(removeBtn);
      pillsContainer.appendChild(pill);
    }
    section.appendChild(pillsContainer);
  }

  // Add tag input
  const addRow = el("div", { class: "vocab-add-row" });
  const addInput = document.createElement("input");
  addInput.type = "text";
  addInput.className = "prefs-input vocab-add-input";
  addInput.placeholder = "Add tag to vocabulary...";
  addRow.appendChild(addInput);

  const addBtn = el("button", { class: "btn btn-primary btn-icon-text" });
  addBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg><span>Add</span>`;
  const doAdd = async () => {
    const name = addInput.value.trim();
    if (!name) return;
    try {
      await addVocabularyTag(name);
      showToast(`Added "${name}"`, "success");
      addInput.value = "";
      load(container);
    } catch {
      showToast("Failed to add tag", "error");
    }
  };
  addBtn.addEventListener("click", doAdd);
  addInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doAdd();
  });
  addRow.appendChild(addBtn);
  section.appendChild(addRow);

  return section;
}

function renderMerge(
  vocab: VocabularyTag[],
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  section.appendChild(el("h2", {}, "Merge Tags"));
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "Combine two tags into one. The source tag is deleted: "
        + "its articles and learned weight are transferred to the target tag."
    )
  );

  const mergeRow = el("div", { class: "vocab-merge-row" });

  const sourceSelect = document.createElement("select");
  sourceSelect.className = "prefs-select";
  const targetSelect = document.createElement("select");
  targetSelect.className = "prefs-select";

  sourceSelect.appendChild(el("option", { value: "" }, "Source (will be deleted)..."));
  targetSelect.appendChild(el("option", { value: "" }, "Target (will be kept)..."));
  for (const tag of vocab) {
    sourceSelect.appendChild(
      el("option", { value: String(tag.id) }, tag.name)
    );
    targetSelect.appendChild(
      el("option", { value: String(tag.id) }, tag.name)
    );
  }

  const mergeBtn = el("button", { class: "btn btn-primary btn-icon-text" });
  mergeBtn.innerHTML = `${ICON_MERGE}<span>Merge</span>`;
  mergeBtn.addEventListener("click", async () => {
    const srcId = Number(sourceSelect.value);
    const tgtId = Number(targetSelect.value);
    if (!srcId || !tgtId) {
      showToast("Select both source and target tags", "error");
      return;
    }
    if (srcId === tgtId) {
      showToast("Cannot merge a tag into itself", "error");
      return;
    }
    const srcName = vocab.find((t) => t.id === srcId)?.name ?? "";
    const tgtName = vocab.find((t) => t.id === tgtId)?.name ?? "";
    try {
      await mergeVocabularyTags(srcId, tgtId);
      showToast(`Merged "${srcName}" into "${tgtName}"`, "success");
      load(container);
    } catch {
      showToast("Failed to merge tags", "error");
    }
  });

  mergeRow.appendChild(sourceSelect);
  mergeRow.appendChild(el("span", { class: "vocab-merge-arrow" }, "\u2192"));
  mergeRow.appendChild(targetSelect);
  mergeRow.appendChild(mergeBtn);
  section.appendChild(mergeRow);

  return section;
}

function renderTagWeights(
  tags: TagWeight[],
  container: HTMLElement
): HTMLElement {
  const section = el("div", { class: "prefs-section" });
  const weightsH2 = el("h2", {}, "Learned Tag Weights ");
  if (tags.length > 0) {
    weightsH2.appendChild(el("span", { class: "section-count" }, String(tags.length)));
  }
  section.appendChild(weightsH2);
  section.appendChild(
    el(
      "p",
      { class: "prefs-hint" },
      "These weights are learned from your feedback. Positive = interesting, negative = not."
    )
  );

  if (tags.length === 0) {
    section.appendChild(
      el(
        "p",
        { class: "prefs-empty" },
        "No tag weights yet. Give feedback on articles to start learning."
      )
    );
    return section;
  }

  let showAll = false;
  const visibleTags = tags.slice(0, DEFAULT_TAG_SHOW);
  const maxWeight = Math.max(...tags.map((t) => Math.abs(t.weight)), 0.01);

  const list = el("div", { class: "tag-weights-list" });

  function renderTags(): void {
    list.innerHTML = "";
    const toShow = showAll ? tags : visibleTags;
    for (const tag of toShow) {
      const row = el("div", { class: "tag-weight-row" });

      const name = el("span", { class: "tag-weight-name" }, tag.name);

      const barContainer = el("div", { class: "tag-weight-bar" });
      const barFill = el("div", {
        class: `tag-weight-bar-fill ${tag.weight >= 0 ? "positive" : "negative"}`,
      });
      const pct = Math.round((Math.abs(tag.weight) / maxWeight) * 100);
      barFill.style.width = `${pct}%`;
      barContainer.appendChild(barFill);

      const weight = el(
        "span",
        {
          class: `tag-weight-value ${tag.weight >= 0 ? "positive" : "negative"}`,
        },
        tag.weight >= 0 ? `+${tag.weight.toFixed(2)}` : tag.weight.toFixed(2)
      );

      const resetBtn = el("button", { class: "btn-reset" });
      resetBtn.innerHTML = ICON_RESET;
      resetBtn.addEventListener("click", async () => {
        try {
          await resetTagWeight(tag.name);
          showToast(`Reset "${tag.name}"`, "success");
          load(container);
        } catch {
          showToast("Failed to reset tag", "error");
        }
      });

      row.appendChild(name);
      row.appendChild(barContainer);
      row.appendChild(weight);
      row.appendChild(resetBtn);
      list.appendChild(row);
    }
  }
  renderTags();
  section.appendChild(list);

  if (tags.length > DEFAULT_TAG_SHOW) {
    const ICON_EXPAND = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`;
    const ICON_COLLAPSE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>`;
    const toggleBtn = el("button", { class: "btn btn-small btn-icon-text" });
    toggleBtn.innerHTML = `${ICON_EXPAND}<span>Show all (${tags.length})</span>`;
    toggleBtn.addEventListener("click", () => {
      showAll = !showAll;
      const icon = showAll ? ICON_COLLAPSE : ICON_EXPAND;
      const label = showAll
        ? `Show top ${DEFAULT_TAG_SHOW}`
        : `Show all (${tags.length})`;
      toggleBtn.innerHTML = `${icon}<span>${label}</span>`;
      renderTags();
    });
    section.appendChild(toggleBtn);
  }

  return section;
}
