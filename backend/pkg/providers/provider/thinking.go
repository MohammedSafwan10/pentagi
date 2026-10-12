package provider

import (
	"context"
	"fmt"
	"maps"
	"slices"

	"pentagi/pkg/providers/pconfig"

	"github.com/vxcontrol/langchaingo/llms"
	"github.com/vxcontrol/langchaingo/llms/streaming"
)

// ThinkingLevels lists levels verified on these OpenAI-compatible models.
// Unknown models keep their configured behavior instead of receiving guessed options.
func ThinkingLevels(model string) []string {
	switch model {
	case "deepseek-v4.1-flash":
		return []string{"none", "low", "medium", "high"}
	case "glm-5.3-flash":
		return []string{"low", "high"}
	case "muse-spark-1.3-contributor":
		return []string{"minimal", "low", "medium", "high"}
	default:
		return []string{}
	}
}

func ValidateThinkingLevel(model, level string) error {
	if !slices.Contains(ThinkingLevels(model), level) {
		return fmt.Errorf("thinking level %q is not supported by %s", level, model)
	}
	return nil
}

type thinkingProvider struct {
	Provider
	level string
}

// WithThinking affects assistant calls only; setup and specialists keep their settings.
func WithThinking(prv Provider, level string) (Provider, error) {
	if previous, ok := prv.(*thinkingProvider); ok {
		prv = previous.Provider
	}
	if err := ValidateThinkingLevel(prv.Model(pconfig.OptionsTypeAssistant), level); err != nil {
		return nil, err
	}
	return &thinkingProvider{Provider: prv, level: level}, nil
}

func (p *thinkingProvider) CallWithTools(ctx context.Context, opt pconfig.ProviderOptionsType, chain []llms.MessageContent, tools []llms.Tool, cb streaming.Callback) (*llms.ContentResponse, error) {
	if opt != pconfig.OptionsTypeAssistant {
		return p.Provider.CallWithTools(ctx, opt, chain, tools, cb)
	}
	body := map[string]any{}
	if config := p.GetProviderConfig(); config != nil && config.Assistant != nil {
		maps.Copy(body, config.Assistant.ExtraBody)
	}
	delete(body, "thinking")
	delete(body, "reasoning")
	body["reasoning_effort"] = p.level
	if p.Model(opt) == "deepseek-v4.1-flash" {
		mode := "enabled"
		if p.level == "none" {
			mode = "disabled"
		}
		body["thinking"] = map[string]any{"type": mode}
	}
	return p.Provider.CallWithExtraOptions(ctx, opt, chain, tools, cb, llms.WithExtraBody(body))
}
