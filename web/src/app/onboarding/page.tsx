"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import type { Grade, Subject, ExamType, ExamSchedule } from "@/types/api";

const STEPS = ["年级", "教材", "排名", "选科", "考试"];
const GRADES: Grade[] = ["高一", "高二", "高三"];
const REQUIRED_SUBJECTS: Subject[] = ["语文", "数学", "英语"];
const ELECTIVE_SUBJECTS: Subject[] = ["物理", "化学", "地理", "政治", "生物", "历史"];
const EXAM_TYPES: ExamType[] = ["周测", "月考", "期中", "期末"];

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [grade, setGrade] = useState<Grade | null>(null);
  const [textbookVersion, setTextbookVersion] = useState("沪教版");
  const [classRank, setClassRank] = useState("");
  const [gradeRank, setGradeRank] = useState("");
  const [classTotal, setClassTotal] = useState("");
  const [gradeTotal, setGradeTotal] = useState("");
  const [electives, setElectives] = useState<Subject[]>([]);
  const [exams, setExams] = useState<ExamSchedule[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const examIdRef = useRef(0);
  const router = useRouter();
  const { toast } = useToast();

  // Restore from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("onboarding_draft");
    if (saved) {
      try {
        const data = JSON.parse(saved);
        if (data.grade) setGrade(data.grade);
        if (data.textbookVersion) setTextbookVersion(data.textbookVersion);
        if (data.electives) setElectives(data.electives);
        if (data.step) setStep(data.step);
      } catch { /* ignore */ }
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem("onboarding_draft", JSON.stringify({ grade, textbookVersion, electives, step }));
  }, [grade, textbookVersion, electives, step, hydrated]);

  function toggleElective(s: Subject) {
    setElectives((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : prev.length < 3 ? [...prev, s] : prev);
  }

  function addExam() {
    const id = ++examIdRef.current;
    setExams((prev) => [...prev, { id, exam_type: "月考", exam_date: "", subjects: [] }]);
  }

  function canNext(): boolean {
    if (step === 0) return !!grade;
    if (step === 1) return !!textbookVersion;
    if (step === 3) return electives.length === 3;
    return true;
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      // Mock API call
      await new Promise((r) => setTimeout(r, 1000));
      localStorage.removeItem("onboarding_draft");
      localStorage.setItem("onboarding_completed", "true");
      toast("建档完成！正在跳转工作台...", "success");
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch {
      toast("提交失败，请重试", "error");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg flex flex-col items-center px-4 py-8 md:py-16">
      <div className="text-center mb-8">
        <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center text-white font-bold text-lg mx-auto mb-3">AI</div>
        <h1 className="text-xl font-bold text-text-primary">欢迎使用 AI 伴学教练</h1>
        <p className="text-sm text-text-secondary mt-1">让我们先了解一下你的学习情况</p>
      </div>

      {/* Step Indicator */}
      <div className="w-full max-w-lg mb-8">
        <div className="flex items-center justify-between">
          {STEPS.map((label, i) => (
            <div key={label} className="flex flex-col items-center flex-1">
              <div className="flex items-center w-full">
                {i > 0 && <div className={cn("flex-1 h-0.5", i <= step ? "bg-primary" : "bg-gray-200")} />}
                <button
                  onClick={() => i < step && setStep(i)}
                  disabled={i > step}
                  className={cn(
                    "w-8 h-8 rounded-full text-xs font-medium flex items-center justify-center shrink-0 transition-colors",
                    i < step ? "bg-success text-white cursor-pointer" :
                    i === step ? "bg-primary text-white" :
                    "bg-gray-200 text-text-tertiary"
                  )}
                >
                  {i < step ? "✓" : i + 1}
                </button>
                {i < STEPS.length - 1 && <div className={cn("flex-1 h-0.5", i < step ? "bg-primary" : "bg-gray-200")} />}
              </div>
              <span className={cn("text-xs mt-1.5", i === step ? "text-primary font-medium" : "text-text-tertiary")}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      <Card className="w-full max-w-lg">
        {/* Step 0: Grade */}
        {step === 0 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-center">你现在是几年级？</h2>
            <div className="grid grid-cols-3 gap-3">
              {GRADES.map((g) => (
                <button
                  key={g}
                  onClick={() => setGrade(g)}
                  className={cn(
                    "py-4 rounded-xl text-sm font-medium border-2 transition-colors",
                    grade === g ? "border-primary bg-primary-light text-primary" : "border-border hover:border-gray-300"
                  )}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 1: Textbook */}
        {step === 1 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-center">选择教材版本</h2>
            <select
              value={textbookVersion}
              onChange={(e) => setTextbookVersion(e.target.value)}
              className="w-full px-3 py-2.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            >
              <option value="沪教版">沪教版</option>
              <option value="人教版">人教版</option>
              <option value="北师大版">北师大版</option>
            </select>
          </div>
        )}

        {/* Step 2: Rank */}
        {step === 2 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-center">排名信息（可选）</h2>
            <p className="text-sm text-text-secondary text-center">帮助我们更好地评估你的学习水平</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-text-secondary mb-1">班级排名</label>
                <input type="number" value={classRank} onChange={(e) => setClassRank(e.target.value)} placeholder="如：15" className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">班级人数</label>
                <input type="number" value={classTotal} onChange={(e) => setClassTotal(e.target.value)} placeholder="如：45" className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">年级排名</label>
                <input type="number" value={gradeRank} onChange={(e) => setGradeRank(e.target.value)} placeholder="如：120" className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
              <div>
                <label className="block text-xs text-text-secondary mb-1">年级人数</label>
                <input type="number" value={gradeTotal} onChange={(e) => setGradeTotal(e.target.value)} placeholder="如：500" className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Subject Combination */}
        {step === 3 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-center">选择选科组合</h2>
            <div>
              <p className="text-xs text-text-secondary mb-2">必修（自动选中）</p>
              <div className="flex gap-2 mb-4">
                {REQUIRED_SUBJECTS.map((s) => (
                  <div key={s} className="px-4 py-2 bg-gray-100 rounded-lg text-sm text-text-tertiary">{s}</div>
                ))}
              </div>
              <p className="text-xs text-text-secondary mb-2">选修（选择 3 门）<span className="text-primary ml-1">已选 {electives.length}/3</span></p>
              <div className="grid grid-cols-3 gap-2">
                {ELECTIVE_SUBJECTS.map((s) => (
                  <button
                    key={s}
                    onClick={() => toggleElective(s)}
                    className={cn(
                      "py-3 rounded-lg text-sm font-medium border-2 transition-colors",
                      electives.includes(s) ? "border-primary bg-primary-light text-primary" : "border-border hover:border-gray-300"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Exam Schedule */}
        {step === 4 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-center">近期考试节点（可选）</h2>
            {exams.map((exam, i) => (
              <div key={exam.id ?? i} className="p-3 border border-border rounded-lg space-y-2">
                <div className="flex gap-2">
                  <select
                    value={exam.exam_type}
                    onChange={(e) => {
                      const updated = [...exams];
                      updated[i] = { ...exam, exam_type: e.target.value as ExamType };
                      setExams(updated);
                    }}
                    className="flex-1 px-3 py-2 border border-border rounded-lg text-sm"
                  >
                    {EXAM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <input
                    type="date"
                    value={exam.exam_date}
                    onChange={(e) => {
                      const updated = [...exams];
                      updated[i] = { ...exam, exam_date: e.target.value };
                      setExams(updated);
                    }}
                    className="flex-1 px-3 py-2 border border-border rounded-lg text-sm"
                  />
                </div>
                <button onClick={() => setExams((prev) => prev.filter((_, j) => j !== i))} className="text-xs text-error hover:underline">删除</button>
              </div>
            ))}
            <Button variant="outline" onClick={addExam} fullWidth>+ 添加考试</Button>
          </div>
        )}

        {/* Navigation buttons */}
        <div className="flex gap-3 mt-8">
          {step > 0 && (
            <Button variant="outline" onClick={() => setStep(step - 1)} className="flex-1">上一步</Button>
          )}
          {step === 2 && (
            <Button variant="ghost" onClick={() => setStep(step + 1)} className="flex-1">跳过</Button>
          )}
          {step === 4 ? (
            <>
              <Button variant="ghost" onClick={handleSubmit} className="flex-1">跳过</Button>
              <Button onClick={handleSubmit} loading={submitting} className="flex-1">完成建档</Button>
            </>
          ) : (
            <Button onClick={() => setStep(step + 1)} disabled={!canNext()} className="flex-1">下一步</Button>
          )}
        </div>
      </Card>
    </div>
  );
}
