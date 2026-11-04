"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Plus, RotateCcw, Save, ShieldCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Badge, Button, Card, ErrorText, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import { keys, useExtractionRules, useOrganizations, useWorkspace } from "@/lib/queries";
import type { CustomRule, RuleConfig, RuleEditor, Severity } from "@/types/api";

const OPERATOR_LABELS: Record<string, string> = {
  is_empty: "is empty",
  is_not_empty: "is not empty",
  equals: "equals",
  not_equals: "does not equal",
  contains: "contains",
  not_contains: "does not contain",
  greater_than: "is greater than",
  less_than: "is less than",
  before: "is before",
  after: "is after",
};
const NO_VALUE = new Set(["is_empty", "is_not_empty"]);

function SeveritySelect({
  value,
  onChange,
  disabled,
}: {
  value: Severity;
  onChange: (s: Severity) => void;
  disabled: boolean;
}) {
  // Fixed-width wrapper: the shared Select is w-full and would otherwise stretch across the row.
  return (
    <div className="w-52 shrink-0">
      <Select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as Severity)}
        className={value === "error" ? "text-red-700" : "text-amber-700"}
        aria-label="Severity"
      >
        <option value="error">Error · blocks approval</option>
        <option value="warning">Warning · flag only</option>
      </Select>
    </div>
  );
}

function newCustomRule(editor: RuleEditor): CustomRule {
  const field = editor.fields[0];
  return {
    enabled: true,
    field: field.key,
    operator: editor.operators[field.type][0],
    value: "",
    severity: "warning",
    message: "",
  };
}

export default function RulesPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();
  const { data: workspace } = useWorkspace(workspaceId);
  const { data: orgs } = useOrganizations();
  const { data: editor, isLoading, error } = useExtractionRules(workspaceId);
  // Unsaved edits; null means "showing exactly what the server has".
  const [draft, setDraft] = useState<RuleConfig | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const role = orgs?.find((o) => o.id === workspace?.organization_id)?.role;
  const canEdit = role === "owner" || role === "admin";

  const save = useMutation({
    mutationFn: (config: RuleConfig) =>
      api<RuleEditor>(`workspaces/${workspaceId}/extraction-rules`, { method: "PUT", json: config }),
    onSuccess: (result) => {
      setDraft(null);
      setSaved(`Saved · ${result.rechecked ?? 0} invoice(s) awaiting review re-checked`);
      queryClient.setQueryData(keys.extractionRules(workspaceId), result);
      queryClient.invalidateQueries({ queryKey: keys.extractions(workspaceId) });
    },
  });

  if (isLoading || !editor) return error ? <ErrorText error={error} /> : <Spinner />;

  const current = draft ?? editor.config;
  const dirty = draft !== null && JSON.stringify(draft) !== JSON.stringify(editor.config);
  const fieldType = (key: string) => editor.fields.find((f) => f.key === key)?.type ?? "text";
  const edit = (change: (config: RuleConfig) => void) => {
    const next = structuredClone(current);
    change(next);
    setDraft(next);
    setSaved(null);
  };

  return (
    <>
      <PageHeader
        title="Validation rules"
        description={`What gets flagged when invoices are reviewed in ${workspace?.name ?? "this workspace"}. Errors block approval; warnings only flag.`}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href={`/w/${workspaceId}/review`}
              className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
            >
              Back to Review
            </Link>
            {canEdit && (
              <>
                <Button variant="secondary" disabled={!dirty} onClick={() => setDraft(null)}>
                  <RotateCcw className="size-4" /> Discard
                </Button>
                <Button disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(current)}>
                  <Save className="size-4" /> Save rules
                </Button>
              </>
            )}
          </div>
        }
      />
      <div className="max-w-5xl space-y-6 p-8">
        {!canEdit && (
          <p className="rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-600">
            You can view these rules. Only owners and admins can change them.
          </p>
        )}
        <ErrorText error={save.error} />
        {saved && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{saved}</p>}

        <Card>
          <div className="flex items-start gap-3 border-b border-slate-200 px-6 py-4">
            <ShieldCheck className="mt-0.5 size-5 text-indigo-600" />
            <div>
              <h2 className="font-semibold">Predefined rules</h2>
              <p className="text-sm text-slate-500">
                Switch checks on or off, choose how serious they are, and tune their limits.
              </p>
            </div>
          </div>
          <ul className="divide-y divide-slate-100">
            {editor.predefined.map((rule) => {
              const setting = current.builtin[rule.key];
              return (
                <li
                  key={rule.key}
                  className={cn("flex flex-wrap items-center gap-4 px-6 py-4", !setting.enabled && "opacity-60")}
                >
                  <label className="flex min-w-64 flex-1 items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 rounded border-slate-300"
                      checked={setting.enabled}
                      disabled={!canEdit}
                      onChange={(e) => edit((c) => (c.builtin[rule.key].enabled = e.target.checked))}
                    />
                    <span>
                      <span className="block text-sm font-medium">{rule.label}</span>
                      <span className="block text-xs text-slate-500">{rule.description}</span>
                    </span>
                  </label>
                  {rule.params.map((param) => (
                    <label key={param.key} className="flex shrink-0 items-center gap-2 text-xs text-slate-600">
                      <span className="max-w-28 text-right">{param.label}</span>
                      <div className={param.type === "gstin" ? "w-44" : "w-28"}>
                        <Input
                          className={param.type === "gstin" ? "font-mono uppercase" : undefined}
                          type={param.type === "number" ? "number" : "text"}
                          min={param.type === "number" ? 0 : undefined}
                          step="any"
                          disabled={!canEdit}
                          placeholder={param.type === "gstin" ? "24AAACS1234A1Z1" : undefined}
                          value={setting.params[param.key] ?? ""}
                          onChange={(e) =>
                            edit((c) => {
                              const raw = e.target.value;
                              c.builtin[rule.key].params[param.key] =
                                raw === "" ? null : param.type === "number" ? Number(raw) : raw;
                            })
                          }
                        />
                      </div>
                    </label>
                  ))}
                  <SeveritySelect
                    value={setting.severity}
                    disabled={!canEdit}
                    onChange={(severity) => edit((c) => (c.builtin[rule.key].severity = severity))}
                  />
                </li>
              );
            })}
          </ul>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-6 py-4">
            <div className="flex items-start gap-3">
              <ListChecks className="mt-0.5 size-5 text-indigo-600" />
              <div>
                <h2 className="font-semibold">Custom rules</h2>
                <p className="text-sm text-slate-500">
                  Your own checks, e.g. “If <em>Total</em> is greater than 50,000 → Warning: needs partner sign-off”.
                </p>
              </div>
            </div>
            {canEdit && (
              <Button variant="secondary" onClick={() => edit((c) => c.custom.push(newCustomRule(editor)))}>
                <Plus className="size-4" /> Add rule
              </Button>
            )}
          </div>
          {current.custom.length === 0 ? (
            <p className="px-6 py-6 text-sm text-slate-500">No custom rules yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {current.custom.map((rule, index) => {
                const type = fieldType(rule.field);
                const operators = editor.operators[type] ?? [];
                return (
                  <li key={rule.id ?? `new-${index}`} className="flex flex-wrap items-center gap-2 px-6 py-3 text-sm">
                    <input
                      type="checkbox"
                      className="size-4 rounded border-slate-300"
                      checked={rule.enabled}
                      disabled={!canEdit}
                      onChange={(e) => edit((c) => (c.custom[index].enabled = e.target.checked))}
                      aria-label="Rule enabled"
                    />
                    <span className="text-slate-500">If</span>
                    <div className="w-40 shrink-0">
                      <Select
                        value={rule.field}
                        disabled={!canEdit}
                        aria-label="Field"
                        onChange={(e) =>
                          edit((c) => {
                            const next = c.custom[index];
                            next.field = e.target.value;
                            const allowed = editor.operators[fieldType(next.field)];
                            if (!allowed.includes(next.operator)) next.operator = allowed[0];
                          })
                        }
                      >
                        {editor.fields.map((f) => (
                          <option key={f.key} value={f.key}>
                            {f.label}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div className="w-40 shrink-0">
                      <Select
                        value={rule.operator}
                        disabled={!canEdit}
                        aria-label="Condition"
                        onChange={(e) => edit((c) => (c.custom[index].operator = e.target.value))}
                      >
                        {operators.map((op) => (
                          <option key={op} value={op}>
                            {OPERATOR_LABELS[op] ?? op}
                          </option>
                        ))}
                      </Select>
                    </div>
                    {!NO_VALUE.has(rule.operator) && (
                      <div className="w-36 shrink-0">
                        <Input
                          type={type === "amount" ? "number" : type === "date" ? "date" : "text"}
                          step="any"
                          value={rule.value ?? ""}
                          disabled={!canEdit}
                          aria-label="Value"
                          placeholder={type === "amount" ? "50000" : "value"}
                          onChange={(e) => edit((c) => (c.custom[index].value = e.target.value))}
                        />
                      </div>
                    )}
                    <span className="text-slate-500">→</span>
                    <SeveritySelect
                      value={rule.severity}
                      disabled={!canEdit}
                      onChange={(severity) => edit((c) => (c.custom[index].severity = severity))}
                    />
                    <div className="min-w-48 flex-1">
                      <Input
                        value={rule.message}
                        maxLength={200}
                        disabled={!canEdit}
                        aria-label="Message shown to the reviewer"
                        placeholder="Message shown to the reviewer"
                        onChange={(e) => edit((c) => (c.custom[index].message = e.target.value))}
                      />
                    </div>
                    {canEdit && (
                      <button
                        onClick={() => edit((c) => c.custom.splice(index, 1))}
                        className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
                        title="Delete rule"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <p className="flex items-center gap-2 text-xs text-slate-400">
          <Badge color="gray">Always on</Badge> Required fields and readable dates/amounts are always checked. Changing
          rules re-checks invoices awaiting review; approved invoices keep the result they were approved with.
        </p>
      </div>
    </>
  );
}
