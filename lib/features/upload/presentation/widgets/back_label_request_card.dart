import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../profile/providers/profile_provider.dart';
import '../../providers/upload_provider.dart';
import '../../services/image_picker_service.dart';

class BackLabelRequestCard extends ConsumerWidget {
  const BackLabelRequestCard({
    super.key,
    required this.analysisId,
    required this.foodId,
    required this.foodName,
  });

  final String? analysisId;
  final String? foodId;
  final String foodName;

  Future<void> _pickFromCamera(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final image =
        await ImagePickerService.instance.pickBackLabelFromCamera();

    if (image == null || !context.mounted) {
      return;
    }

    await _uploadLabel(
      context: context,
      ref: ref,
      imagePath: image.path,
    );
  }

  Future<void> _pickFromGallery(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final image =
        await ImagePickerService.instance.pickBackLabelFromGallery();

    if (image == null || !context.mounted) {
      return;
    }

    await _uploadLabel(
      context: context,
      ref: ref,
      imagePath: image.path,
    );
  }

  Future<void> _uploadLabel({
    required BuildContext context,
    required WidgetRef ref,
    required String imagePath,
  }) async {
    final resolvedAnalysisId = analysisId?.trim();
    final resolvedFoodId = foodId?.trim();

    if (resolvedAnalysisId == null ||
        resolvedAnalysisId.isEmpty ||
        resolvedFoodId == null ||
        resolvedFoodId.isEmpty) {
      _showMessage(
        context,
        'The analysis session is incomplete. Please restart the analysis.',
      );
      return;
    }

    final profilePayload =
        ref.read(profileProvider).backendPayload;

    await ref.read(uploadProvider.notifier).uploadBackLabel(
          imagePath: imagePath,
          analysisId: resolvedAnalysisId,
          foodId: resolvedFoodId,
          userProfile: profilePayload,
        );
  }

  void _showMessage(
    BuildContext context,
    String message,
  ) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
        ),
      );
  }

  @override
  Widget build(
    BuildContext context,
    WidgetRef ref,
  ) {
    final theme = Theme.of(context);
    final uploadState = ref.watch(uploadProvider);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: theme.colorScheme.tertiary.withOpacity(0.25),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: theme.colorScheme.tertiary,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.document_scanner_rounded,
                  color: theme.colorScheme.onTertiary,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Nutrition label required',
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                        color:
                            theme.colorScheme.onTertiaryContainer,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'The backend detected $foodName as a branded product.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color:
                            theme.colorScheme.onTertiaryContainer,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            'Upload a clear photo of the back label showing the nutrition facts and ingredients. Quinone will continue the existing analysis.',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onTertiaryContainer,
            ),
          ),
          const SizedBox(height: 18),
          _LabelTips(
            textColor:
                theme.colorScheme.onTertiaryContainer,
          ),
          const SizedBox(height: 22),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: uploadState.isUploading
                  ? null
                  : () => _pickFromCamera(
                        context,
                        ref,
                      ),
              icon: const Icon(
                Icons.camera_alt_rounded,
              ),
              label: const Text(
                'Take label photo',
              ),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: uploadState.isUploading
                  ? null
                  : () => _pickFromGallery(
                        context,
                        ref,
                      ),
              icon: const Icon(
                Icons.photo_library_outlined,
              ),
              label: const Text(
                'Choose from gallery',
              ),
            ),
          ),
          if (uploadState.isUploading) ...[
            const SizedBox(height: 18),
            LinearProgressIndicator(
              value: uploadState.uploadProgress > 0
                  ? uploadState.uploadProgress
                  : null,
            ),
            const SizedBox(height: 10),
            Text(
              'Uploading nutrition label…',
              style: theme.textTheme.bodyMedium?.copyWith(
                color:
                    theme.colorScheme.onTertiaryContainer,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LabelTips extends StatelessWidget {
  const _LabelTips({
    required this.textColor,
  });

  final Color textColor;

  @override
  Widget build(BuildContext context) {
    const tips = <String>[
      'Keep the complete label inside the frame.',
      'Make sure text and numbers are readable.',
      'Avoid glare, shadows, and motion blur.',
      'Include the ingredient list when possible.',
    ];

    return Column(
      children: [
        for (var index = 0; index < tips.length; index++) ...[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.check_circle_outline_rounded,
                size: 19,
                color: textColor,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  tips[index],
                  style: Theme.of(context)
                      .textTheme
                      .bodyMedium
                      ?.copyWith(
                        color: textColor,
                      ),
                ),
              ),
            ],
          ),
          if (index < tips.length - 1)
            const SizedBox(height: 10),
        ],
      ],
    );
  }
}
