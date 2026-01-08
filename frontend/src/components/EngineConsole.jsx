import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/hooks/use-toast";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function metricBadgeVariant(value) {
  if (value >= 50) return "default";
  if (value >= 25) return "secondary";
  return "outline";
}

export default function EngineConsole() {
  const [objective, setObjective] = useState(
    "Build an MVP multi-agent context compression engine with STM/CWM/LTM, compression triggers, retrieval-based rehydration, and token reduction metrics."
  );
  const [scenario, setScenario] = useState("C");
  const [useLlm, setUseLlm] = useState(true);

  const [runId, setRunId] = useState(null);
  const [creating, setCreating] = useState(false);

  const [userMessage, setUserMessage] = useState("");
  const [sending, setSending] = useState(false);

  const [events, setEvents] = useState([]);
  const [memory, setMemory] = useState(null);

  const [demoRunning, setDemoRunning] = useState(false);

  const bottomRef = useRef(null);

  const canChat = Boolean(runId);

  const metrics = useMemo(() => memory?.metrics || {}, [memory]);

  const refresh = async (rid) => {
    if (!rid) return;
    const [evRes, memRes] = await Promise.all([
      axios.get(`${API}/runs/${rid}/events`),
      axios.get(`${API}/runs/${rid}/memory`),
    ]);
    setEvents(evRes.data.events || []);
    setMemory(memRes.data);
  };

  useEffect(() => {
    if (!runId) return;
    refresh(runId);
  }, [runId]);

  useEffect(() => {
    if (!bottomRef.current) return;
    bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  const createRun = async () => {
    setCreating(true);
    try {
      const res = await axios.post(`${API}/runs`, {
        objective,
        scenario,
        config: {
          use_llm: useLlm,
          stm_max_messages: 12,
          compression_token_threshold: 2400,
          compression_interval_steps: 3,
          llm_provider: "openai",
          llm_model: "gpt-5.2",
        },
      });
      setRunId(res.data.run_id);
      toast({ title: "Run created", description: res.data.run_id });
    } catch (e) {
      console.error(e);
      toast({
        title: "Failed to create run",
        description: e?.response?.data?.detail || e.message,
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  const sendStep = async () => {
    if (!userMessage.trim()) return;
    setSending(true);
    try {
      const res = await axios.post(`${API}/runs/${runId}/step`, {
        user_message: userMessage,
      });
      setUserMessage("");
      await refresh(runId);
      if (res.data.triggered_compression) {
        toast({ title: "Compression triggered", description: "CWM updated" });
      }
    } catch (e) {
      console.error(e);
      toast({
        title: "Step failed",
        description: e?.response?.data?.detail || e.message,
        variant: "destructive",
      });
    } finally {
      setSending(false);
    }
  };

  const forceCompress = async () => {
    try {
      await axios.post(`${API}/runs/${runId}/compress`);
      await refresh(runId);
      toast({ title: "Compression forced", description: "Snapshot written" });
    } catch (e) {
      toast({
        title: "Compression failed",
        description: e?.response?.data?.detail || e.message,
        variant: "destructive",
      });
    }
  };

  const runDemo = async () => {
    setDemoRunning(true);
    try {
      const res = await axios.post(`${API}/demo/run`, {
        objective,
        scenario,
        config: {
          use_llm: useLlm,
          stm_max_messages: 12,
          compression_token_threshold: 1800,
          compression_interval_steps: 2,
          llm_provider: "openai",
          llm_model: "gpt-5.2",
        },
      });
      setRunId(res.data.run_id);
      await refresh(res.data.run_id);
      toast({ title: "Demo complete", description: `${res.data.count} steps` });
    } catch (e) {
      toast({
        title: "Demo failed",
        description: e?.response?.data?.detail || e.message,
        variant: "destructive",
      });
    } finally {
      setDemoRunning(false);
    }
  };

  const EventCard = ({ evt }) => {
    const type = evt.type;
    const header =
      type === "planner"
        ? "Planner"
        : type === "critic"
        ? "Critic"
        : type === "retrieval"
        ? "Retrieval"
        : type === "compression"
        ? "Compression"
        : type === "snapshot"
        ? "Snapshot"
        : type;

    let preview = "";
    if (type === "planner") preview = evt.payload?.assistant_message || "";
    if (type === "critic") preview = `${evt.payload?.verdict || ""}`;
    if (type === "retrieval") preview = evt.payload?.retrieval?.notes || "";
    if (type === "snapshot") preview = evt.payload?.path || "";
    if (type === "compression") preview = "CWM updated";

    return (
      <Card
        data-testid={`event-card-${evt.id}`}
        className="border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/40"
      >
        <CardHeader className="py-3">
          <div className="flex items-center justify-between gap-3">
            <CardTitle
              data-testid={`event-title-${evt.id}`}
              className="text-base"
            >
              {header}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Badge
                data-testid={`event-step-badge-${evt.id}`}
                variant="secondary"
              >
                step {evt.step_index}
              </Badge>
              <Badge data-testid={`event-type-badge-${evt.id}`} variant="outline">
                {type}
              </Badge>
            </div>
          </div>
          {preview ? (
            <div
              data-testid={`event-preview-${evt.id}`}
              className="text-sm text-muted-foreground line-clamp-2"
            >
              {preview}
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="pt-0 pb-4">
          <details data-testid={`event-details-${evt.id}`} className="group">
            <summary
              data-testid={`event-details-summary-${evt.id}`}
              className="cursor-pointer select-none text-sm text-foreground/80"
            >
              View payload
            </summary>
            <pre
              data-testid={`event-payload-${evt.id}`}
              className="mt-3 overflow-auto rounded-md bg-muted/60 p-3 text-xs leading-relaxed"
            >
              {JSON.stringify(evt.payload, null, 2)}
            </pre>
          </details>
        </CardContent>
      </Card>
    );
  };

  return (
    <div
      data-testid="engine-console"
      className="min-h-screen bg-[radial-gradient(60%_60%_at_20%_15%,rgba(124,58,237,0.16),transparent),radial-gradient(55%_55%_at_80%_25%,rgba(20,184,166,0.14),transparent),radial-gradient(45%_45%_at_55%_80%,rgba(244,114,182,0.12),transparent)]"
    >
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-col gap-2">
          <h1
            data-testid="page-title"
            className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight"
          >
            Context Distillery
          </h1>
          <p
            data-testid="page-subtitle"
            className="text-base md:text-lg text-muted-foreground max-w-3xl"
          >
            Multi-agent context compression engine (MVP): STM → structured CWM → selective
            rehydration, with inspectable logs and token-reduction metrics.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6">
          <Card
            data-testid="setup-card"
            className="lg:col-span-5 border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/40"
          >
            <CardHeader>
              <CardTitle data-testid="setup-title" className="text-lg">
                Run setup
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label
                  data-testid="objective-label"
                  className="text-sm text-foreground/80"
                >
                  Objective
                </label>
                <Textarea
                  data-testid="objective-input"
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  className="min-h-[120px]"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label
                    data-testid="scenario-label"
                    className="text-sm text-foreground/80"
                  >
                    Demo scenario
                  </label>
                  <div className="flex gap-2">
                    <Button
                      data-testid="scenario-c-button"
                      type="button"
                      variant={scenario === "C" ? "default" : "secondary"}
                      onClick={() => setScenario("C")}
                      className="rounded-full"
                    >
                      C (self-demo)
                    </Button>
                    <Button
                      data-testid="scenario-a-button"
                      type="button"
                      variant={scenario === "A" ? "default" : "secondary"}
                      onClick={() => setScenario("A")}
                      className="rounded-full"
                    >
                      A (spec)
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <label
                    data-testid="llm-toggle-label"
                    className="text-sm text-foreground/80"
                  >
                    Engine mode
                  </label>
                  <div className="flex gap-2">
                    <Button
                      data-testid="llm-on-button"
                      type="button"
                      variant={useLlm ? "default" : "secondary"}
                      onClick={() => setUseLlm(true)}
                      className="rounded-full"
                    >
                      LLM on
                    </Button>
                    <Button
                      data-testid="llm-off-button"
                      type="button"
                      variant={!useLlm ? "default" : "secondary"}
                      onClick={() => setUseLlm(false)}
                      className="rounded-full"
                    >
                      Strict deterministic
                    </Button>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  data-testid="create-run-button"
                  onClick={createRun}
                  disabled={creating}
                  className="rounded-full"
                >
                  {creating ? "Creating…" : "Create run"}
                </Button>
                <Button
                  data-testid="run-demo-button"
                  onClick={runDemo}
                  disabled={demoRunning}
                  variant="secondary"
                  className="rounded-full"
                >
                  {demoRunning ? "Running demo…" : "Run demo"}
                </Button>

                <div className="flex items-center gap-2 ml-auto">
                  <Badge data-testid="run-id-badge" variant="outline">
                    {runId ? `run: ${runId}` : "no run"}
                  </Badge>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <label
                  data-testid="chat-label"
                  className="text-sm text-foreground/80"
                >
                  Send a step
                </label>
                <div className="flex gap-2">
                  <Input
                    data-testid="chat-input"
                    value={userMessage}
                    onChange={(e) => setUserMessage(e.target.value)}
                    placeholder={
                      canChat
                        ? "Type a message… (try changing a constraint mid-run)"
                        : "Create a run first"
                    }
                    disabled={!canChat}
                  />
                  <Button
                    data-testid="send-step-button"
                    onClick={sendStep}
                    disabled={!canChat || sending}
                    className="rounded-full"
                  >
                    {sending ? "Sending…" : "Send"}
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Button
                    data-testid="force-compress-button"
                    onClick={forceCompress}
                    disabled={!canChat}
                    variant="outline"
                    className="rounded-full"
                  >
                    Force compress
                  </Button>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <div
                  data-testid="metrics-title"
                  className="text-sm text-foreground/80"
                >
                  Metrics
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge data-testid="metric-baseline" variant="outline">
                    baseline ~{metrics.baseline_tokens ?? 0} tok
                  </Badge>
                  <Badge data-testid="metric-injected" variant="outline">
                    injected ~{metrics.injected_tokens ?? 0} tok
                  </Badge>
                  <Badge
                    data-testid="metric-reduction"
                    variant={metricBadgeVariant(metrics.reduction_pct ?? 0)}
                  >
                    reduction {(metrics.reduction_pct ?? 0).toFixed(1)}%
                  </Badge>
                  <Badge data-testid="metric-critic" variant="secondary">
                    critic {metrics.critic_verdict || "—"}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="lg:col-span-7 space-y-6">
            <Card
              data-testid="events-card"
              className="border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/40"
            >
              <CardHeader>
                <CardTitle data-testid="events-title" className="text-lg">
                  Event timeline
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea
                  data-testid="events-scroll"
                  className="h-[420px] pr-4"
                >
                  <div className="space-y-3" data-testid="events-list">
                    {events.length === 0 ? (
                      <div
                        data-testid="events-empty"
                        className="text-sm text-muted-foreground"
                      >
                        No events yet. Create a run or run the demo.
                      </div>
                    ) : null}
                    {events.map((evt) => (
                      <EventCard key={evt.id} evt={evt} />
                    ))}
                    <div ref={bottomRef} />
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            <Card
              data-testid="memory-card"
              className="border-border/60 bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/40"
            >
              <CardHeader>
                <CardTitle data-testid="memory-title" className="text-lg">
                  Memory viewer
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="cwm" data-testid="memory-tabs">
                  <TabsList data-testid="memory-tabs-list" className="grid grid-cols-3">
                    <TabsTrigger data-testid="tab-stm" value="stm">
                      STM
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-cwm" value="cwm">
                      CWM
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-metrics" value="metrics">
                      Metrics
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent data-testid="tab-stm-content" value="stm">
                    <div className="mt-3 rounded-lg border border-border/60 bg-muted/40 p-3">
                      <pre
                        data-testid="stm-pre"
                        className="text-xs overflow-auto max-h-[260px]"
                      >
                        {JSON.stringify(memory?.stm || [], null, 2)}
                      </pre>
                    </div>
                  </TabsContent>

                  <TabsContent data-testid="tab-cwm-content" value="cwm">
                    <div className="mt-3 rounded-lg border border-border/60 bg-muted/40 p-3">
                      <pre
                        data-testid="cwm-pre"
                        className="text-xs overflow-auto max-h-[260px]"
                      >
                        {JSON.stringify(memory?.cwm || {}, null, 2)}
                      </pre>
                    </div>
                  </TabsContent>

                  <TabsContent data-testid="tab-metrics-content" value="metrics">
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="rounded-lg border border-border/60 bg-muted/40 p-3">
                        <div
                          data-testid="metrics-explainer-title"
                          className="text-sm font-medium"
                        >
                          What we measure
                        </div>
                        <div
                          data-testid="metrics-explainer"
                          className="text-sm text-muted-foreground mt-2"
                        >
                          <ReactMarkdown>
                            {`- **baseline_tokens**: full transcript injected (estimate)\n- **injected_tokens**: retrieved memory injected (estimate)\n- **reduction_pct**: token reduction (target ≥ 50%)\n- **critic**: verification agent verdict\n`}
                          </ReactMarkdown>
                        </div>
                      </div>
                      <div className="rounded-lg border border-border/60 bg-muted/40 p-3">
                        <div
                          data-testid="snapshot-path-title"
                          className="text-sm font-medium"
                        >
                          Latest snapshot
                        </div>
                        <div
                          data-testid="snapshot-path"
                          className="text-sm text-muted-foreground mt-2 break-all"
                        >
                          {metrics.last_snapshot_path || "—"}
                        </div>
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
