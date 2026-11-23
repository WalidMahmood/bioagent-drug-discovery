import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyFlipAction,
  computeTargetPriorityScore,
  evaluateMoaConcordance,
  sanitizeDiseaseContext,
  sanitizeGeneSymbol,
} from "./discoveryAudit";

test("classifyFlipAction assigns inhibit for upregulated and restore for downregulated genes", () => {
  const up = classifyFlipAction(2.4);
  assert.equal(up.expected_moa_class, "inhibitory");
  assert.match(up.recommended_flip, /Turn OFF/i);

  const down = classifyFlipAction(-1.9);
  assert.equal(down.expected_moa_class, "activating");
  assert.match(down.recommended_flip, /Turn ON/i);
});

test("evaluateMoaConcordance allows concordant drugs and hard-blocks discordant MoAs", () => {
  const okInhib = evaluateMoaConcordance(2.8, "INHIBITOR", "EGFR tyrosine kinase inhibitor");
  assert.equal(okInhib.status, "CONCORDANT");

  const blockedAgonist = evaluateMoaConcordance(2.8, "AGONIST", "Receptor agonist");
  assert.equal(blockedAgonist.status, "DISCORDANT_BLOCKED");

  const blockedInhibitorOnDown = evaluateMoaConcordance(-2.3, "INHIBITOR", "Small molecule inhibitor");
  assert.equal(blockedInhibitorOnDown.status, "DISCORDANT_BLOCKED");

  const okAgonistOnDown = evaluateMoaConcordance(-2.3, "ACTIVATOR", "Pathway activator");
  assert.equal(okAgonistOnDown.status, "CONCORDANT");
});

test("computeTargetPriorityScore rewards approved concordant drugs and penalizes pan-essential toxicity", () => {
  const tier1 = computeTargetPriorityScore({
    log2FC: 2.9,
    padj: 1e-12,
    topDiseaseScore: 0.85,
    maxConcordantStageRank: 4,
    tractableModalities: ["SM", "AB"],
    isEssential: false,
    safetyLiabilityCount: 0,
  });
  assert.equal(tier1.evidence_tier, "Tier 1: Approved Drug Repurposing");
  assert.ok(tier1.total_score >= 90);

  const risky = computeTargetPriorityScore({
    log2FC: 1.2,
    padj: null,
    topDiseaseScore: 0.1,
    maxConcordantStageRank: -1,
    tractableModalities: [],
    isEssential: true,
    safetyLiabilityCount: 12,
  });
  assert.equal(risky.evidence_tier, "Tier 3: Novel Genetic Flip Target");
  assert.equal(risky.breakdown.safety_selectivity_0_20, 2.0);
  assert.ok(risky.total_score < tier1.total_score);
});

test("sanitizers reject unsafe symbols and clean disease text", () => {
  assert.equal(sanitizeGeneSymbol("egfr"), "EGFR");
  assert.equal(sanitizeGeneSymbol("../etc/passwd"), null);
  assert.equal(sanitizeGeneSymbol("A"), null);
  assert.equal(sanitizeDiseaseContext("Breast Cancer; DROP TABLE"), "Breast Cancer DROP TABLE");
});
