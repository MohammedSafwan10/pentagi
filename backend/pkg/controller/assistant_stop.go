package controller

import (
	"context"
	"fmt"

	"pentagi/pkg/database"
)

// StopAssistant handles both reserved sessions and workers already running.
func (fc *flowController) StopAssistant(ctx context.Context, flowID, assistantID int64) (database.Assistant, error) {
	assistant, err := fc.db.GetFlowAssistant(ctx, database.GetFlowAssistantParams{ID: assistantID, FlowID: flowID})
	if err != nil {
		return database.Assistant{}, err
	}
	fc.mx.Lock()
	cancelPreparing := fc.preparingAssistants[assistantID]
	entry := fc.flows[flowID]
	var fw FlowWorker
	if entry != nil {
		fw = entry.worker
	}
	fc.mx.Unlock()

	if cancelPreparing != nil {
		if assistant.Status == database.AssistantStatusRunning && fw != nil {
			if aw, getErr := fw.GetAssistant(ctx, assistantID); getErr == nil {
				if err := aw.Stop(ctx); err != nil {
					return database.Assistant{}, err
				}
				return fc.db.GetFlowAssistant(ctx, database.GetFlowAssistantParams{ID: assistantID, FlowID: flowID})
			}
		}
		cancelPreparing()
		if fw != nil {
			if aw, getErr := fw.GetAssistant(ctx, assistantID); getErr == nil {
				if err := aw.Finish(ctx); err != nil {
					return database.Assistant{}, err
				}
			}
		}
		assistant, err = fc.db.UpdateAssistantStatus(ctx, database.UpdateAssistantStatusParams{ID: assistantID, Status: database.AssistantStatusFinished})
		if err != nil {
			return database.Assistant{}, err
		}
		flow, err := fc.db.GetFlow(ctx, flowID)
		if err != nil {
			return database.Assistant{}, err
		}
		fc.subs.NewFlowPublisher(flow.UserID, flowID).AssistantUpdated(ctx, assistant)
		return assistant, nil
	}
	if assistant.Status == database.AssistantStatusFinished || assistant.Status == database.AssistantStatusFailed || assistant.Status == database.AssistantStatusWaiting {
		return assistant, nil
	}
	if fw == nil {
		fw, err = fc.GetFlow(ctx, flowID)
		if err != nil {
			return database.Assistant{}, err
		}
	}
	aw, err := fw.GetAssistant(ctx, assistantID)
	if err != nil {
		return database.Assistant{}, fmt.Errorf("assistant %d is not ready to stop: %w", assistantID, err)
	}
	if err := aw.Stop(ctx); err != nil {
		return database.Assistant{}, err
	}
	return fc.db.GetFlowAssistant(ctx, database.GetFlowAssistantParams{ID: assistantID, FlowID: flowID})
}
