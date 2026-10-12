package provider

import (
	"context"
	"testing"

	"pentagi/pkg/providers/pconfig"

	"github.com/stretchr/testify/require"
	"github.com/vxcontrol/langchaingo/llms"
	"github.com/vxcontrol/langchaingo/llms/streaming"
)

type thinkingRecorder struct {
	Provider
	model  string
	body   map[string]any
	extra  map[string]any
	direct bool
}

func (p *thinkingRecorder) Model(pconfig.ProviderOptionsType) string { return p.model }
func (p *thinkingRecorder) GetProviderConfig() *pconfig.ProviderConfig {
	return &pconfig.ProviderConfig{Assistant: &pconfig.AgentConfig{ExtraBody: p.extra}}
}
func (p *thinkingRecorder) CallWithTools(context.Context, pconfig.ProviderOptionsType, []llms.MessageContent, []llms.Tool, streaming.Callback) (*llms.ContentResponse, error) {
	p.direct = true
	return &llms.ContentResponse{}, nil
}
func (p *thinkingRecorder) CallWithExtraOptions(_ context.Context, _ pconfig.ProviderOptionsType, _ []llms.MessageContent, _ []llms.Tool, _ streaming.Callback, extra ...llms.CallOption) (*llms.ContentResponse, error) {
	var options llms.CallOptions
	for _, option := range extra {
		option(&options)
	}
	p.body = llms.ExtraBody(options)
	return &llms.ContentResponse{}, nil
}

func TestThinking_WireAndSpecialistIsolation(t *testing.T) {
	for _, model := range []string{"deepseek-v4.1-flash", "glm-5.3-flash", "muse-spark-1.3-contributor"} {
		for _, level := range ThinkingLevels(model) {
			t.Run(model+"/"+level, func(t *testing.T) {
				original := map[string]any{"thinking": map[string]any{"type": "disabled"}, "custom": true}
				recorder := &thinkingRecorder{model: model, extra: original}
				prv, err := WithThinking(recorder, level)
				require.NoError(t, err)
				_, err = prv.CallWithTools(context.Background(), pconfig.OptionsTypeAssistant, nil, nil, nil)
				require.NoError(t, err)
				require.Equal(t, level, recorder.body["reasoning_effort"])
				require.Equal(t, true, recorder.body["custom"])
				require.Equal(t, map[string]any{"type": "disabled"}, original["thinking"])
				if model == "deepseek-v4.1-flash" {
					want := "enabled"
					if level == "none" {
						want = "disabled"
					}
					require.Equal(t, map[string]any{"type": want}, recorder.body["thinking"])
				} else {
					require.NotContains(t, recorder.body, "thinking")
				}
				_, err = prv.CallWithTools(context.Background(), pconfig.OptionsTypeCoder, nil, nil, nil)
				require.NoError(t, err)
				require.True(t, recorder.direct)
			})
		}
	}
}

func TestThinking_RejectsUnsupportedAndReplacesPreviousLevel(t *testing.T) {
	require.Error(t, ValidateThinkingLevel("glm-5.3-flash", "none"))
	require.Error(t, ValidateThinkingLevel("glm-5.3-flash", "medium"))
	_, err := WithThinking(&thinkingRecorder{model: "muse-spark-1.3-contributor"}, "none")
	require.Error(t, err)
	_, err = WithThinking(&thinkingRecorder{model: "unknown"}, "high")
	require.Error(t, err)
	recorder := &thinkingRecorder{model: "deepseek-v4.1-flash"}
	prv, err := WithThinking(recorder, "high")
	require.NoError(t, err)
	prv, err = WithThinking(prv, "none")
	require.NoError(t, err)
	_, err = prv.CallWithTools(context.Background(), pconfig.OptionsTypeAssistant, nil, nil, nil)
	require.NoError(t, err)
	require.Equal(t, "none", recorder.body["reasoning_effort"])
}
