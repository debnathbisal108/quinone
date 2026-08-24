import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../profile/providers/profile_provider.dart';
import '../../../recipe/models/manual_recipe.dart';
import '../../providers/upload_provider.dart';
import '../widgets/analyze_button.dart';
import '../../services/image_picker_service.dart';
import '../../services/background_analysis_service.dart';
import '../widgets/back_label_request_card.dart';
import '../widgets/image_grid.dart';
import '../widgets/upload_progress_card.dart';
import '../widgets/upload_source_sheet.dart';
import '../widgets/nutrition_label_source_sheet.dart';

class UploadScreen extends ConsumerStatefulWidget {
  const UploadScreen({super.key, this.initialBackgroundResponse});

  final Map<String, dynamic>? initialBackgroundResponse;

  @override
  ConsumerState<UploadScreen> createState() =>
      _UploadScreenState();
}

class _UploadScreenState extends ConsumerState<UploadScreen> {
  bool _handledResponse = false;

  @override
  void initState() {
    super.initState();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }

      final initial = widget.initialBackgroundResponse;
      if (initial != null && initial.isNotEmpty) {
        ref.read(uploadProvider.notifier).restoreResponse(initial);
        _handleUploadResponse();
      } else {
        ref.read(uploadProvider.notifier).reset();
      }
    });
  }

  void _showImageSourceSheet() {
    final uploadState = ref.read(uploadProvider);

    if (uploadState.isUploading) {
      return;
    }

    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) => const UploadSourceSheet(),
    );
  }

  Future<void> _startAnalysis() async {
    final uploadState = ref.read(uploadProvider);

    if (uploadState.images.isEmpty) {
      _showMessage(
        'Add at least one food image before starting.',
      );
      return;
    }

    if (uploadState.isUploading) {
      return;
    }

    _handledResponse = false;

    final profilePayload =
        ref.read(profileProvider).backendPayload;

    await ref.read(uploadProvider.notifier).upload(
          userProfile: profilePayload,
        );

    if (!mounted) {
      return;
    }

    _handleUploadResponse();
  }

  void _showLabelSourceSheet() {
    if (ref.read(uploadProvider).isUploading) return;
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) => NutritionLabelSourceSheet(
        onSelected: _startLabelOnlyAnalysis,
      ),
    );
  }

  Future<void> _startLabelOnlyAnalysis(String imagePath) async {
    final uploadState = ref.read(uploadProvider);
    if (uploadState.isUploading || imagePath.trim().isEmpty) return;
    _handledResponse = false;
    final profilePayload = ref.read(profileProvider).backendPayload;
    await ref.read(uploadProvider.notifier).uploadLabelOnly(
          imagePath: imagePath,
          userProfile: profilePayload,
        );
    if (!mounted) return;
    _handleUploadResponse();
  }

  void _handleUploadResponse() {
    if (_handledResponse || !mounted) {
      return;
    }

    final response = ref.read(uploadProvider).response;
    final data = _normalizeResponseData(response?.data);

    if (response == null) {
      return;
    }

    if (data == null) {
      _handledResponse = true;

      _showMessage(
        'The server returned an unsupported response.',
      );
      return;
    }

    final status = data['status']
        ?.toString()
        .trim()
        .toLowerCase();

    // Keep the foreground-service notification alive when Quinone is in
    // the background so the user can see the completed state and tap it to
    // return. When the app is already visible, clean it up immediately.
    final appIsVisible =
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    if (appIsVisible) {
      unawaited(BackgroundAnalysisService.instance.stopAndClear());
    }

    if (status == 'waiting_for_back_label') {
      _handledResponse = true;
      return;
    }


    if (status == 'waiting_for_serving_confirmation') {
      _handledResponse = true;
      context.push(
        '/serving-confirmation',
        extra: data,
      );
      return;
    }


    if (status == 'waiting_for_meal_confirmation') {
      final rawDraft = data['meal_draft'];
      if (rawDraft is! Map) {
        _handledResponse = true;
        _showMessage('The server returned an invalid meal draft.');
        return;
      }

      try {
        final recipe = ManualRecipe.fromJson(
          Map<String, dynamic>.from(rawDraft),
        );
        _handledResponse = true;
        context.push(
          '/recipe',
          extra: {
            'recipe': recipe.toJson(),
            'photo_review': true,
            'analysis_id': data['analysis_id']?.toString(),
            if (data['label_items'] is List)
              'label_items': data['label_items'],
          },
        );
      } catch (_) {
        _handledResponse = true;
        _showMessage('Couldn’t prepare the detected meal for review.');
      }
      return;
    }

    if (_isFinalResponse(status, data)) {
      _handledResponse = true;

      context.push(
        '/result',
        extra: data,
      );

      return;
    }

    _handledResponse = true;

    final serverMessage =
        data['message']?.toString().trim();

    if (serverMessage != null &&
        serverMessage.isNotEmpty) {
      _showMessage(serverMessage);
    }
  }

  Map<String, dynamic>? _normalizeResponseData(
    dynamic data,
  ) {
    if (data is Map<String, dynamic>) {
      return data;
    }

    if (data is Map) {
      return Map<String, dynamic>.from(data);
    }

    return null;
  }

  Map<String, dynamic> _readBackLabelRequest(
    Map<String, dynamic> responseData,
  ) {
    return _findBackLabelRequest(responseData) ??
        const <String, dynamic>{};
  }

  Map<String, dynamic>? _findBackLabelRequest(
    dynamic value,
  ) {
    if (value is List) {
      for (final item in value) {
        final result = _findBackLabelRequest(item);

        if (result != null) {
          return result;
        }
      }

      return null;
    }

    if (value is! Map) {
      return null;
    }

    final map = Map<String, dynamic>.from(value);

    const preferredKeys = [
      'back_label_request',
      'label_request',
      'nutrition_label_request',
      'requested_label',
      'branded_product',
      'target_food',
      'food_requiring_label',
    ];

    for (final key in preferredKeys) {
      final nested = map[key];

      if (nested is Map) {
        return Map<String, dynamic>.from(nested);
      }
    }

    final containsFoodIdentifier =
        _firstNonEmptyText([
          map['food_id'],
          map['target_food_id'],
          map['id'],
        ]) !=
        null;

    final containsFoodName =
        _firstNonEmptyText([
          map['food_name'],
          map['product_name'],
          map['name'],
        ]) !=
        null;

    if (containsFoodIdentifier && containsFoodName) {
      return map;
    }

    for (final nestedValue in map.values) {
      final result = _findBackLabelRequest(nestedValue);

      if (result != null) {
        return result;
      }
    }

    return null;
  }

  String? _firstNonEmptyText(
    List<dynamic> values,
  ) {
    for (final value in values) {
      if (value == null) {
        continue;
      }

      final text = value.toString().trim();

      if (text.isNotEmpty &&
          text.toLowerCase() != 'null') {
        return text;
      }
    }

    return null;
  }

  bool _isFinalResponse(
    String? status,
    Map<String, dynamic> data,
  ) {
    const completedStatuses = {
      'completed',
      'complete',
      'success',
      'finished',
      'analysis_complete',
    };

    if (status != null &&
        completedStatuses.contains(status)) {
      return true;
    }

    return data.containsKey('health_scores') ||
        data.containsKey('final_result') ||
        data.containsKey('nutrition') ||
        data.containsKey('meal_analysis');
  }

  void _showMessage(String message) {
    if (!mounted) {
      return;
    }

    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
        ),
      );
  }

  Future<void> _confirmClearImages() async {
    final uploadState = ref.read(uploadProvider);

    if (uploadState.images.isEmpty ||
        uploadState.isUploading) {
      return;
    }

    final shouldClear = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Remove all images?'),
          content: const Text(
            'All selected meal images will be removed.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(false);
              },
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
              },
              child: const Text('Remove all'),
            ),
          ],
        );
      },
    );

    if (shouldClear != true || !mounted) {
      return;
    }

    _handledResponse = false;

    ref.read(uploadProvider.notifier).clearImages();
  }

  void _cancelUpload() {
    ref.read(uploadProvider.notifier).cancelUpload();
  }

  @override
  Widget build(BuildContext context) {
    final uploadState = ref.watch(uploadProvider);
    final profileState = ref.watch(profileProvider);

    final responseData = _normalizeResponseData(
      uploadState.response?.data,
    );

    final responseStatus = responseData?['status']
        ?.toString()
        .trim()
        .toLowerCase();

    final isWaitingForLabel =
        responseStatus == 'waiting_for_back_label';

    final backLabelRequest = responseData == null
        ? const <String, dynamic>{}
        : _readBackLabelRequest(responseData);

    final resolvedAnalysisId = _firstNonEmptyText([
      responseData?['analysis_id'],
      backLabelRequest['analysis_id'],
      uploadState.analysisId,
    ]);

    final resolvedFoodId = _firstNonEmptyText([
      backLabelRequest['food_id'],
      backLabelRequest['target_food_id'],
      backLabelRequest['id'],
      responseData?['food_id'],
      responseData?['target_food_id'],
      uploadState.foodId,
    ]);

    final resolvedFoodName = _firstNonEmptyText([
          backLabelRequest['food_name'],
          backLabelRequest['name'],
          backLabelRequest['product_name'],
          responseData?['food_name'],
          responseData?['product_name'],
        ]) ??
        'Branded food';

    ref.listen<UploadState>(
      uploadProvider,
      (previous, next) {
        final responseChanged =
            previous?.response != next.response;

        if (responseChanged && next.response != null) {
          // A back-label continuation produces a new response.
          // Reset the guard so that response can be processed.
          _handledResponse = false;

          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              _handleUploadResponse();
            }
          });
        }

        final errorChanged =
            previous?.error != next.error;

        if (errorChanged &&
            next.error != null &&
            next.error!.trim().isNotEmpty) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              _showMessage(next.error!);
            }
          });
        }
      },
    );

    return PopScope(
      canPop: !uploadState.isUploading,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && uploadState.isUploading) {
          _showMessage(
            'Cancel the current upload before leaving.',
          );
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Analyze food'),
          actions: [
            if (uploadState.images.isNotEmpty &&
                !isWaitingForLabel)
              IconButton(
                tooltip: 'Remove all images',
                onPressed: uploadState.isUploading
                    ? null
                    : _confirmClearImages,
                icon: const Icon(
                  Icons.delete_outline_rounded,
                ),
              ),
          ],
        ),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
              20,
              16,
              20,
              32,
            ),
            children: [
              _UploadHeader(
                hasProfile: profileState.hasProfile,
              ),
              const SizedBox(height: 24),

              if (!isWaitingForLabel) ...[
                Row(
                  children: [
                    Expanded(
                      child: _AddImagesCard(
                        enabled: !uploadState.isUploading,
                        onPressed: _showImageSourceSheet,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _AddLabelCard(
                        enabled: !uploadState.isUploading,
                        onPressed: _showLabelSourceSheet,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                ImageGrid(
                  images: uploadState.images,
                  enabled: !uploadState.isUploading,
                  onRemove: (imageId) {
                    ref
                        .read(uploadProvider.notifier)
                        .removeImage(imageId);
                  },
                  onReorder: (oldIndex, newIndex) {
                    ref
                        .read(uploadProvider.notifier)
                        .reorderImages(
                          oldIndex,
                          newIndex,
                        );
                  },
                ),
              ],

              if (uploadState.isUploading) ...[
                const SizedBox(height: 24),
                UploadProgressCard(
                  progress: uploadState.uploadProgress,
                  message: uploadState.progressMessage,
                  stage: uploadState.progressStage,
                  onCancel: _cancelUpload,
                ),
              ],

              if (isWaitingForLabel &&
                  responseData != null &&
                  !uploadState.isUploading) ...[
                const SizedBox(height: 8),
                BackLabelRequestCard(
                  analysisId: resolvedAnalysisId,
                  foodId: resolvedFoodId,
                  foodName: resolvedFoodName,
                ),
              ],

              if (!uploadState.isUploading &&
                  !isWaitingForLabel) ...[
                const SizedBox(height: 28),
                // AnalyzeButton(
                //   enabled: uploadState.images.isNotEmpty,
                //   isLoading: false,
                //   onPressed: _startAnalysis,
                // ),
                AnalyzeButton(
                  enabled: uploadState.images.isNotEmpty,
                  loading: false,
                  onPressed: _startAnalysis,
                ),
              ],

              if (!uploadState.isUploading &&
                  uploadState.images.isEmpty &&
                  !isWaitingForLabel) ...[
                const SizedBox(height: 18),
                const _PhotographyTips(),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _UploadHeader extends StatelessWidget {
  final bool hasProfile;

  const _UploadHeader({
    required this.hasProfile,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'What are you eating?',
          style: theme.textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Photo first. Review before analysis.',
          style: theme.textTheme.bodyLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 9,
          ),
          decoration: BoxDecoration(
            color: hasProfile
                ? theme.colorScheme.primaryContainer
                : theme
                    .colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                hasProfile
                    ? Icons.person_rounded
                    : Icons.person_outline_rounded,
                size: 18,
                color: hasProfile
                    ? theme
                        .colorScheme.onPrimaryContainer
                    : theme
                        .colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  hasProfile
                      ? 'Personalized'
                      : 'General targets',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: hasProfile
                        ? theme
                            .colorScheme.onPrimaryContainer
                        : theme
                            .colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _AddImagesCard extends StatelessWidget {
  final bool enabled;
  final VoidCallback onPressed;

  const _AddImagesCard({
    required this.enabled,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(24),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: enabled ? onPressed : null,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(
            horizontal: 24,
            vertical: 30,
          ),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: theme.colorScheme.outlineVariant,
            ),
          ),
          child: Column(
            children: [
              Container(
                width: 62,
                height: 62,
                decoration: BoxDecoration(
                  color:
                      theme.colorScheme.primaryContainer,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Icon(
                  Icons.add_a_photo_rounded,
                  size: 30,
                  color: theme
                      .colorScheme.onPrimaryContainer,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Add meal images',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Use your camera or choose from gallery',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color:
                      theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AddLabelCard extends StatelessWidget {
  const _AddLabelCard({required this.enabled, required this.onPressed});
  final bool enabled;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(24),
      child: InkWell(
        onTap: enabled ? onPressed : null,
        borderRadius: BorderRadius.circular(24),
        child: Container(
          height: 188,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: theme.colorScheme.outlineVariant),
          ),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(color: theme.colorScheme.secondaryContainer, shape: BoxShape.circle),
              child: Icon(Icons.document_scanner_rounded, color: theme.colorScheme.onSecondaryContainer),
            ),
            const SizedBox(height: 12),
            Text('Nutrition label', textAlign: TextAlign.center, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text('Packaged food', textAlign: TextAlign.center, style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          ]),
        ),
      ),
    );
  }
}

class _PhotographyTips extends StatelessWidget {
  const _PhotographyTips();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    const tips = [
      (
        Icons.light_mode_outlined,
        'Use bright, natural lighting',
      ),
      (
        Icons.center_focus_strong_rounded,
        'Keep the entire meal visible',
      ),
      (
        Icons.inventory_2_outlined,
        'Show branded packaging when available',
      ),
    ];

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'For better results',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          for (var index = 0;
              index < tips.length;
              index++) ...[
            Row(
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Icon(
                  tips[index].$1,
                  size: 20,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    tips[index].$2,
                    style: theme.textTheme.bodyMedium,
                  ),
                ),
              ],
            ),
            if (index < tips.length - 1)
              const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}
