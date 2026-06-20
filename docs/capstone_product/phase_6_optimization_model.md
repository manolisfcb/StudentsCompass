# Phase 6: Formal Optimization Model

## 1. Purpose

Phase 6 is the mathematical core of StudentsCompass.

The product question is not only:

```text
Which courses look useful for this student?
```

The optimization question is:

```text
Which feasible set and sequence of courses maximizes career readiness for a
target role, given the student's current skill gaps, labor-market value,
budget, available time, course quality, prerequisites, and redundancy?
```

This phase turns the learning route from a heuristic recommendation into a
defensible constrained optimization model. The output must be explainable:
every selected course should have a mathematical reason, every rejected course
should be traceable to either lower marginal value or a violated constraint, and
the final route should be reproducible from the same inputs.

## 2. Existing Inputs From Earlier Phases

The model depends on previous capstone phases:

- Phase 1 defines the academic problem and the student-to-role readiness goal.
- Phase 2 provides the learning route API and the first heuristic optimizer.
- Phase 4 extracts and normalizes student skills from resumes.
- Phase 5 assigns a priority score to each missing skill.

The most important inherited input is:

```text
skill_gap_score_s
```

for each missing skill `s`. It estimates how important it is to close that gap,
combining role importance, market demand, and any weak evidence already found in
the student's resume.

Phase 6 does not replace Phase 5. It uses Phase 5 as the value layer and adds
formal decision logic over course selection and sequencing.

## 3. Sets And Indices

```text
S = set of missing skills for the target role
C = set of candidate courses that cover at least one skill in S
E = set of course-skill coverage links, where (i, s) in E if course i covers skill s
K = subset of S containing critical skills
P = set of prerequisite course pairs, where (i, j) in P means course i must precede course j
D = ordered difficulty levels: beginner < intermediate < advanced
G = set of equivalence groups for courses with nearly identical skill coverage
```

Indices:

```text
i, j = courses in C
s = skills in S
g = course equivalence group in G
```

## 4. Parameters

All numeric parameters should be normalized before optimization. In the CP-SAT
implementation, decimal values are scaled to integers, for example by
multiplying by `1000`.

### 4.1 Student And Role Parameters

```text
gap_s in [0, 1.35]
```

Phase 5 skill gap score for skill `s`. Higher means the skill is more important
for this student-role pair.

```text
importance_s in [0, 1]
```

Role-level importance of skill `s`.

```text
demand_s in [0, 1]
```

Labor-market demand signal for skill `s`, derived from synced job postings or
external market data when available.

```text
salary_s in [0, 1]
```

Estimated salary or compensation impact of skill `s`. If salary data is missing,
set `salary_s = 0` and let `gap_s` and `demand_s` drive the model.

```text
critical_s in {0, 1}
```

Whether skill `s` is a critical requirement for the target role.

### 4.2 Course Parameters

```text
coverage_is in [0, 1]
```

Expected coverage strength from course `i` to skill `s`. This comes from the
course-skill mapping table. If a course is linked to a skill but has no explicit
coverage score, the default MVP value is `0.5`.

```text
cost_i >= 0
```

Course cost in the request currency or normalized base currency.

```text
hours_i >= 0
```

Estimated time required to complete course `i`.

```text
rating_i in [0, 1]
```

Course quality signal. A 5-star course becomes `1.0`. Missing rating defaults to
neutral `0.0` unless a catalog-quality prior is introduced.

```text
difficulty_i in {1, 2, 3}
```

Difficulty rank:

```text
1 = beginner
2 = intermediate
3 = advanced
```

```text
catalog_trust_i in [0, 1]
```

Optional catalog confidence score. It can represent provider trust, metadata
completeness, freshness, or manual approval. If unavailable, use `1.0` for active
courses and `0.0` for inactive courses.

### 4.3 User Constraints

```text
B = maximum budget
H = maximum available learning hours
N = maximum number of selected courses
L = minimum number of critical skills to cover
```

If the user omits a constraint:

```text
B = +infinity
H = +infinity
N = product default, initially 5
L = 0 unless the role policy defines a higher minimum
```

### 4.4 Objective Weights

The model uses explicit weights so the defense can explain the optimization
tradeoff:

```text
alpha = weight for role gap closure
beta  = weight for labor-market demand
gamma = weight for salary impact
delta = weight for critical skill coverage
eta   = weight for course quality
lambda_cost = penalty weight for cost
lambda_time = penalty weight for time
lambda_redundancy = penalty weight for redundant coverage
lambda_difficulty = penalty weight for difficulty jumps
lambda_uncovered = penalty weight for leaving high-value skills uncovered
```

Recommended initial values:

```text
alpha = 100
beta = 35
gamma = 25
delta = 50
eta = 8
lambda_cost = 10
lambda_time = 10
lambda_redundancy = 20
lambda_difficulty = 15
lambda_uncovered = 120
```

These are not arbitrary magic numbers. They encode the product judgment that:

- closing a high-priority skill gap is the primary goal;
- critical skills should receive a strong bonus;
- labor-market and salary signals should influence selection without
  overpowering direct role fit;
- cost, time, and redundancy should matter because the route must be realistic;
- leaving a high-value gap uncovered should be more expensive than selecting a
  merely convenient course.

Weights should be calibrated in Phase 7 by comparing against baselines.

## 5. Decision Variables

### 5.1 Course Selection

```text
x_i in {0, 1}
```

`x_i = 1` if course `i` is selected in the learning route.

Why it exists:

This is the main decision variable. The optimizer is choosing a subset of
courses, not ranking courses independently.

### 5.2 Skill Coverage

```text
y_s in {0, 1}
```

`y_s = 1` if skill `s` is considered covered by the selected route.

Why it exists:

This lets the model optimize for covered skills directly and report which gaps
are closed.

```text
u_s >= 0
```

Aggregate coverage units for skill `s` from all selected courses.

Mathematically:

```text
u_s = sum over i where (i,s) in E of coverage_is * x_i
```

Why it exists:

Some skills may be partially covered by several courses. The model needs the
coverage amount, not only a yes/no selected link.

### 5.3 Redundancy

```text
r_s >= 0
```

Redundant coverage above the useful threshold for skill `s`.

Why it exists:

Two courses covering the same skill can be useful up to a point, but after the
coverage threshold is met, extra overlap often wastes time and budget. This
variable penalizes routes that repeatedly teach the same skill while ignoring
other gaps.

### 5.4 Uncovered Gap

```text
m_s in {0, 1}
```

`m_s = 1` if skill `s` remains uncovered.

Why it exists:

This creates an explicit penalty for leaving important skills unresolved. It is
especially important when constraints are tight and the model cannot cover
everything.

### 5.5 Sequence Position

```text
pos_i in {0, 1, ..., N}
```

Recommended position of course `i` in the final route. If `x_i = 0`, then
`pos_i = 0`. If `x_i = 1`, then `pos_i >= 1`.

Why it exists:

The route must be actionable. A set of selected courses is not enough; students
need an order.

### 5.6 Course Pair Ordering

```text
before_ij in {0, 1}
```

`before_ij = 1` if selected course `i` is placed before selected course `j`.

Why it exists:

This supports prerequisite constraints and difficulty progression constraints.

### 5.7 Difficulty Violation

```text
diff_violation_ij in {0, 1}
```

`diff_violation_ij = 1` if the route places a harder course before an easier
course without a prerequisite reason.

Why it exists:

Difficulty order is not always a hard rule. Sometimes an advanced course is
valuable enough to appear early. The variable allows a soft penalty instead of
rejecting the route entirely.

## 6. Coverage Thresholds

A skill should not count as covered merely because a course mentions it.

Define:

```text
theta_s = minimum aggregate coverage needed to consider skill s covered
```

Recommended default:

```text
theta_s = 0.70 for normal skills
theta_s = 0.85 for critical skills
```

Critical skills need stronger evidence before the system claims the student has
a credible route to close the gap.

## 7. Objective Function

The optimization maximizes total route utility:

```text
Maximize Z =
  role_gap_value
  + labor_market_value
  + salary_value
  + critical_skill_value
  + course_quality_value
  - cost_penalty
  - time_penalty
  - redundancy_penalty
  - difficulty_penalty
  - uncovered_gap_penalty
```

Expanded:

```text
Maximize Z =
  alpha * sum_s(gap_s * y_s)
  + beta * sum_s(demand_s * y_s)
  + gamma * sum_s(salary_s * y_s)
  + delta * sum_s(critical_s * y_s)
  + eta * sum_i(rating_i * catalog_trust_i * x_i)
  - lambda_cost * (sum_i(cost_i * x_i) / max(B, 1))
  - lambda_time * (sum_i(hours_i * x_i) / max(H, 1))
  - lambda_redundancy * sum_s(r_s * gap_s)
  - lambda_difficulty * sum_(i,j)(diff_violation_ij)
  - lambda_uncovered * sum_s(gap_s * m_s)
```

### 7.1 Why Each Objective Component Exists

```text
alpha * sum_s(gap_s * y_s)
```

Rewards closing the highest-priority missing skills. This is the core academic
readiness objective.

```text
beta * sum_s(demand_s * y_s)
```

Rewards coverage of skills that appear frequently in the labor market. This
connects the route to employer demand.

```text
gamma * sum_s(salary_s * y_s)
```

Rewards skills associated with higher compensation or stronger economic value.
This makes the optimizer career-outcome aware.

```text
delta * sum_s(critical_s * y_s)
```

Rewards must-have skills for the target role. This prevents the route from
optimizing only broad, easy-to-cover skills.

```text
eta * sum_i(rating_i * catalog_trust_i * x_i)
```

Rewards high-quality courses. A course is not valuable only because it covers a
skill; the route should prefer better learning materials when choices are
otherwise similar.

```text
lambda_cost * normalized total cost
```

Penalizes expensive routes. The model already has a hard budget constraint, but
inside the feasible region, lower cost is still preferable.

```text
lambda_time * normalized total hours
```

Penalizes long routes. Again, the hard time limit prevents infeasible routes,
but the model should prefer efficient routes when value is comparable.

```text
lambda_redundancy * redundant coverage
```

Penalizes repeatedly covering the same skill after the threshold has been met.
This increases breadth and reduces waste.

```text
lambda_difficulty * difficulty violations
```

Penalizes unnatural sequencing, such as advanced material before foundations,
unless the route gains enough value to justify it.

```text
lambda_uncovered * uncovered high-value gaps
```

Penalizes leaving important gaps unresolved. This is what makes the model honest
under constraints: it can return remaining gaps, but it must pay for them in the
objective.

## 8. Hard Constraints

Hard constraints define feasibility. A route that violates any hard constraint
is not allowed.

### 8.1 Budget Constraint

```text
sum_i(cost_i * x_i) <= B
```

Why:

The recommendation must respect the student's financial limit.

### 8.2 Time Constraint

```text
sum_i(hours_i * x_i) <= H
```

Why:

The recommendation must respect the student's available study time.

### 8.3 Maximum Course Count

```text
sum_i(x_i) <= N
```

Why:

The route must stay usable. A mathematically high-value route with too many
courses is not actionable.

### 8.4 Skill Coverage Definition

```text
u_s = sum_i(coverage_is * x_i) for all s in S
```

If `(i, s)` is not in `E`, then `coverage_is = 0`.

Why:

This links course selections to skill outcomes.

### 8.5 Covered Skill Activation

Let:

```text
M_s = sum_i(coverage_is)
epsilon = smallest scaled coverage unit, for example 0.001 before integer scaling
```

```text
u_s >= theta_s * y_s for all s in S
```

```text
u_s <= theta_s - epsilon + M_s * y_s for all s in S
```

In CP-SAT, this can be implemented with enforcement literals:

```text
y_s = 1 => u_s >= theta_s
y_s = 0 => u_s <= theta_s - epsilon
```

Why:

The model can only claim a skill is covered when selected courses provide enough
aggregate coverage.

### 8.6 Uncovered Gap Link

```text
m_s = 1 - y_s for all s in S
```

Why:

Every missing skill is either covered or remains a gap. This gives clean
explanations and clean projected readiness calculations.

### 8.7 Critical Skill Minimum

```text
sum_s(critical_s * y_s) >= L
```

Why:

Some roles require specific core capabilities. If the route cannot cover a
minimum number of them, the optimizer should either find another route or report
that no feasible route satisfies the requirement.

### 8.8 Active Course Constraint

```text
x_i <= active_i
```

where `active_i in {0, 1}`.

Why:

Inactive courses, deprecated links, or unavailable resources cannot appear in
the final route.

### 8.9 Equivalent Course Group Constraint

For each group `g` of equivalent or near-duplicate courses:

```text
sum_i in group g (x_i) <= 1
```

Why:

The optimizer should not select multiple versions of effectively the same
course unless the catalog explicitly marks them as complementary.

### 8.10 Prerequisite Course Constraint

For every `(i, j) in P` where course `i` is a prerequisite for course `j`:

```text
x_j <= x_i
```

Why:

If the route includes an advanced course that requires a prerequisite course,
the prerequisite must also be selected.

### 8.11 Prerequisite Ordering Constraint

For every `(i, j) in P`:

```text
pos_i + 1 <= pos_j + M * (2 - x_i - x_j)
```

Why:

When both courses are selected, the prerequisite must appear earlier in the
sequence.

### 8.12 Position Activation

```text
x_i = 0 => pos_i = 0
x_i = 1 => 1 <= pos_i <= N
```

Why:

Only selected courses receive route positions.

### 8.13 Unique Sequence Positions

For selected courses `i != j`, positions must be different. The conceptual
constraint is:

```text
pos_i != pos_j
```

Because unselected courses all have `pos_i = 0`, a direct `AllDifferent` over
all courses would be wrong. The CP-SAT implementation should use pairwise
ordering variables:

```text
before_ij + before_ji >= x_i + x_j - 1
before_ij <= x_i
before_ij <= x_j
before_ji <= x_i
before_ji <= x_j
```

If `before_ij = 1`, enforce:

```text
pos_i + 1 <= pos_j
```

If `before_ji = 1`, enforce:

```text
pos_j + 1 <= pos_i
```

Equivalently, with big-M:

```text
pos_i + 1 <= pos_j + M * (1 - before_ij)
pos_j + 1 <= pos_i + M * (1 - before_ji)
```

Why:

The route needs one clear sequence, not multiple courses occupying the same
step.

## 9. Soft Constraints And Penalties

Soft constraints can be violated, but the model pays a penalty. This is useful
when reality is messy and strict rules would make the problem infeasible.

### 9.1 Redundancy Definition

```text
r_s >= u_s - 1
r_s >= 0
```

Why:

Coverage above `1.0` means the route is repeatedly covering the same skill. This
can be acceptable, but only if the extra courses add enough value elsewhere.

### 9.2 Difficulty Progression

If course `i` is harder than course `j` and `i` is placed before `j`, then:

```text
diff_violation_ij = 1
```

Conceptually:

```text
difficulty_i > difficulty_j and pos_i < pos_j => diff_violation_ij = 1
```

Why:

Beginner material should usually precede intermediate and advanced material.
This improves route usability without making difficulty order an absolute rule.

### 9.3 Diversity Of Skill Coverage

Optional:

```text
sum_s(y_s) >= minimum_distinct_skills
```

or a soft reward:

```text
diversity_bonus * sum_s(y_s)
```

Why:

This prevents a route from over-optimizing one very valuable skill while leaving
many adjacent skills untouched.

### 9.4 Course Load Balance

Optional:

```text
hours_i * x_i <= max_single_course_hours
```

Why:

One extremely long course may dominate the route. This constraint can keep the
plan more modular.

## 10. CP-SAT Implementation Notes

OR-Tools CP-SAT optimizes integer expressions. Therefore:

1. Normalize every score to a known range.
2. Scale decimal scores to integers:

```text
scaled_value = round(value * SCALE)
SCALE = 1000
```

3. Express the objective as a single integer linear expression.
4. Use boolean enforcement literals for conditional constraints.
5. Store the solver status, objective value, selected variables, and violated
   soft constraints in the optimization run.

Expected objective version name:

```text
cp_sat_route_v1
```

Recommended solver settings:

```text
max_time_in_seconds = 10
num_search_workers = available CPU workers
random_seed = fixed seed for reproducible tests
```

Solver statuses should map to product behavior:

```text
OPTIMAL    => return optimal route
FEASIBLE   => return best route found with status note
INFEASIBLE => return empty route plus infeasibility explanation
UNKNOWN    => return best incumbent if available, otherwise controlled empty route
```

## 11. Output Contract

The route output should include:

```text
objective_version
solver_status
objective_value
match_score_before
projected_match_score_after
total_cost
total_hours
selected_courses
covered_skills
remaining_gaps
route_summary
model_explanation
```

Each selected course should include:

```text
course_id
title
provider
cost
duration_hours
difficulty
rating
optimization_score_contribution
sequence_order
covered_priority_skills
selection_reason
constraint_notes
```

Each covered skill should include:

```text
skill_id
display_name
gap_score
coverage_amount
coverage_threshold
covered_by_course_ids
labor_market_demand
salary_impact
critical
```

Each remaining gap should include:

```text
skill_id
display_name
gap_score
reason_uncovered
```

Common `reason_uncovered` values:

```text
no_course_available
budget_constraint
time_constraint
max_courses_constraint
low_marginal_value
prerequisite_not_satisfied
```

## 12. Explainability Method

For each selected course `i`, compute:

```text
course_value_i =
  sum_s covered by i (
    alpha * gap_s
    + beta * demand_s
    + gamma * salary_s
    + delta * critical_s
  ) * marginal_coverage_is
  + eta * rating_i * catalog_trust_i
```

Then compute:

```text
course_penalty_i =
  lambda_cost * normalized_cost_i
  + lambda_time * normalized_hours_i
  + allocated_redundancy_penalty_i
  + allocated_difficulty_penalty_i
```

And:

```text
net_contribution_i = course_value_i - course_penalty_i
```

Student-facing explanation:

```text
Selected because it covers [skill names], including [critical/high-demand
skills], with net value [net_contribution_i], while staying within budget and
time constraints.
```

Academic explanation:

```text
Course i was selected because x_i = 1 in the optimal feasible solution and its
marginal contribution to covered weighted skill value exceeded its normalized
cost, time, redundancy, and difficulty penalties.
```

## 13. Projected Readiness Score

The projected readiness score should remain separate from the solver objective.
The objective chooses the route; the projected readiness score explains expected
student improvement.

Let:

```text
current_score = match_score_before
total_gap_value = sum_s(gap_s)
covered_gap_value = sum_s(gap_s * min(u_s, 1))
```

Then:

```text
projected_gain =
  (1 - current_score) * covered_gap_value / total_gap_value
```

```text
projected_match_score_after =
  min(1, current_score + projected_gain)
```

Why:

The student cannot gain more than the remaining gap to full readiness. The gain
is proportional to the weighted share of missing skills addressed by the route.

## 14. Infeasibility Handling

The model must be honest when no route satisfies the constraints.

If infeasible, return:

```text
selected_courses = []
solver_status = INFEASIBLE
route_summary = "No feasible route satisfies the current budget, time, course count, and critical-skill constraints."
```

The explanation should identify the tightest blockers:

```text
minimum_required_budget
minimum_required_hours
courses_available_for_critical_skills
critical_skills_without_any_course
```

This is important for trust. A rigorous system should say when the constraints
make the problem impossible instead of pretending to recommend a route.

## 15. Validation Plan

Phase 6 should include tests for:

- budget is never exceeded;
- available hours are never exceeded;
- max course count is never exceeded;
- inactive courses are never selected;
- duplicate equivalent courses are not selected together;
- critical skill minimum is enforced when feasible;
- prerequisite courses are selected before dependent courses;
- covered skills meet their coverage threshold;
- uncovered skills are reported with a reason;
- solver returns the same route for the same seeded input;
- infeasible requests return a controlled empty route;
- CP-SAT route beats or ties heuristic baseline on weighted objective value for
  synthetic cases designed for the model.

## 16. Baseline Comparison For Phase 7

The Phase 6 model should be evaluated against:

- cheapest courses;
- highest-rated courses;
- most popular courses;
- semantic similarity only;
- current heuristic route optimizer;
- random feasible route selection.

Metrics:

```text
weighted skill coverage
critical skill coverage
projected readiness gain
total cost
total hours
score per dollar
score per hour
redundancy rate
constraint satisfaction rate
solver runtime
explanation completeness
```

Expected academic claim:

```text
The CP-SAT optimizer produces a feasible learning route that improves weighted
skill-gap coverage and critical-skill coverage under practical student
constraints, while remaining explainable and reproducible.
```

## 17. MVP-To-Full Model Path

Current implementation status:

- `cp_sat_route_v1` is implemented in `ORToolsLearningRouteOptimizer`.
- OR-Tools is declared as a project dependency.
- The service uses CP-SAT automatically when OR-Tools is installed.
- The service falls back to `heuristic_route_v1` if OR-Tools is unavailable.
- The implemented CP-SAT model optimizes course selection with hard budget,
  hour, and max-course constraints.
- The implemented CP-SAT model assigns route sequence positions inside the
  solver, not as post-processing.
- The implemented CP-SAT model enforces unique selected-course positions.
- The implemented CP-SAT model enforces beginner/intermediate/advanced
  difficulty progression when courses of different difficulty are selected.
- The implemented CP-SAT model uses `is_prerequisite` course-skill links as
  prerequisite/foundation signals and orders those courses earlier when they do
  not conflict with difficulty progression.
- The implemented CP-SAT model covers skill coverage thresholds, uncovered
  skills, aggregate coverage, redundancy, weighted gap value, market demand,
  critical-skill value, course quality, cost penalty, time penalty, redundancy
  penalty, uncovered-gap penalty, and sequence-position value.
- Synthetic evidence for these behaviors is documented in
  `phase_6_validation_evidence.md`.

The first implementation scope is:

- `x_i`, `y_s`, `u_s`, `m_s`, and `r_s`;
- budget, time, max course, active course, coverage threshold, and redundancy
  constraints;
- objective terms for gap value, demand, critical skills, course quality, cost,
  time, redundancy, and uncovered gaps.

The next full-model increments are:

- salary impact when reliable salary data exists;
- richer infeasibility diagnostics.
- explicit course-to-course prerequisite pairs when the catalog stores direct
  dependency edges instead of only skill-level prerequisite signals.

This phased implementation keeps the model academically rigorous while allowing
safe delivery inside the existing StudentsCompass architecture.
