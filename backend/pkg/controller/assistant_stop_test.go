package controller

import (
	"context"
	"database/sql"
	"sync"
	"testing"

	"github.com/stretchr/testify/require"
	"pentagi/pkg/database"
)

type preparingStopQuerier struct {
	database.Querier
	assistant database.Assistant
}

func (q *preparingStopQuerier) GetFlowAssistant(_ context.Context, args database.GetFlowAssistantParams) (database.Assistant, error) {
	if args.ID != q.assistant.ID || args.FlowID != q.assistant.FlowID {
		return database.Assistant{}, sql.ErrNoRows
	}
	return q.assistant, nil
}
func (q *preparingStopQuerier) UpdateAssistantStatus(_ context.Context, args database.UpdateAssistantStatusParams) (database.Assistant, error) {
	q.assistant.Status = args.Status
	return q.assistant, nil
}
func (q *preparingStopQuerier) GetFlow(context.Context, int64) (database.Flow, error) {
	return database.Flow{ID: q.assistant.FlowID, UserID: 1}, nil
}

func TestStopAssistant_CancelsPreparationBeforeWorkerExists(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	q := &preparingStopQuerier{assistant: database.Assistant{ID: 7, FlowID: 4, Status: database.AssistantStatusCreated}}
	fc := &flowController{db: q, mx: &sync.Mutex{}, flows: make(map[int64]*flowEntry),
		preparingAssistants: map[int64]context.CancelFunc{7: cancel},
		subs:                &cascadeFakeSubscriptions{pub: &cascadeFakePublisher{}}}
	stopped, err := fc.StopAssistant(context.Background(), 4, 7)
	require.NoError(t, err)
	require.ErrorIs(t, ctx.Err(), context.Canceled)
	require.Equal(t, database.AssistantStatusFinished, stopped.Status)
}

func TestStopAssistant_DoesNotCancelAssistantOnAnotherFlow(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	q := &preparingStopQuerier{assistant: database.Assistant{ID: 7, FlowID: 4, Status: database.AssistantStatusCreated}}
	fc := &flowController{db: q, mx: &sync.Mutex{}, preparingAssistants: map[int64]context.CancelFunc{7: cancel}}
	_, err := fc.StopAssistant(context.Background(), 99, 7)
	require.ErrorIs(t, err, sql.ErrNoRows)
	require.NoError(t, ctx.Err())
}
