# Live Validation Results — batch-20260826T210045Z-6492b09a

Reviewed: 30/30
Directional verdict: **NO_GO**

> Stratified reviewed sample; metrics are not unbiased market-wide estimates.

## Metrics

```json
{
  "sampling_warning": "Stratified reviewed sample; metrics are not unbiased market-wide estimates.",
  "reviewed": 30,
  "sample_size": 30,
  "sufficient_for_directional_verdict": true,
  "top_stratum": {
    "reviewed": 20,
    "strict_top_apply_rate": 0.35,
    "top_attention_acceptance": 0.35
  },
  "reviewed_sample": {
    "strict_apply_recall": 1.0,
    "shortlist_apply_recall": 1.0,
    "ranking_agreement": 0.4,
    "recommendation_confusion_matrix": {
      "APPLY": {
        "DONT_APPLY": 17,
        "APPLY": 8
      },
      "LOW_PRIORITY": {
        "DONT_APPLY": 4
      },
      "REVIEW": {
        "DONT_APPLY": 1
      }
    }
  },
  "below_cutoff": {
    "reviewed": 10,
    "human_apply_count": 1,
    "human_apply_false_negative_count": 0,
    "human_apply_false_negative_rate": 0.0,
    "missed_attention_count": 0
  },
  "by_tier": {
    "TOP": {
      "count": 19,
      "apply_rate": 0.3157894736842105,
      "attention_acceptance": 0.3157894736842105
    },
    "HIGH": {
      "count": 6,
      "apply_rate": 0.3333333333333333,
      "attention_acceptance": 0.3333333333333333
    },
    "LOW": {
      "count": 4,
      "apply_rate": 0.0,
      "attention_acceptance": 0.0
    },
    "REVIEW": {
      "count": 1,
      "apply_rate": 0.0,
      "attention_acceptance": 0.0
    }
  },
  "semantic_operation": null,
  "market_operation": {
    "active_jobs": 431,
    "detail_missing_jobs": 25,
    "ELIGIBLE": 331,
    "UNCERTAIN": 75,
    "INELIGIBLE": 0,
    "latest_run_event_counts": {
      "CLOSED": 1,
      "TITLE_CHANGED": 1,
      "DESCRIPTION_CHANGED": 5,
      "DEPARTMENT_CHANGED": 2,
      "EMPLOYMENT_TYPE_CHANGED": 2,
      "NEW": 342
    },
    "source_failures_or_incomplete": [
      {
        "company_id": "allegro",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "cisco",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "csob",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "deutsche_boerse_group",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "ey",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "johnson_johnson",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "pure_storage",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "red_hat",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "sap",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "schneider_electric",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "siemens",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "wpp",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      },
      {
        "company_id": "wrike",
        "status": "SUCCESS",
        "inventory_complete": true,
        "details_complete": false,
        "error_type": null,
        "error_message": null
      }
    ]
  },
  "disagreements": {
    "DETERMINISTIC_ELIGIBILITY_ISSUE": {
      "DONT_APPLY": 11,
      "TOP": 6,
      "HIGH": 4,
      "LOW": 1
    },
    "UNREPRESENTED_HUMAN_PREFERENCE": {
      "DONT_APPLY": 7,
      "TOP": 6,
      "HIGH": 1
    },
    "SEMANTIC_INTERPRETATION_ERROR": {
      "DONT_APPLY": 2,
      "TOP": 2
    },
    "BENCHMARK_OR_TAXONOMY_LIMITATION": {
      "DONT_APPLY": 1,
      "TOP": 1
    },
    "SCORING_WEIGHT_OR_CALIBRATION": {
      "DONT_APPLY": 1,
      "HIGH": 1
    }
  },
  "verdict": "NO_GO",
  "verdict_note": "Experimental directional gate, not a production SLA."
}
```
