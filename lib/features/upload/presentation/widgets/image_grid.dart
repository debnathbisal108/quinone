import 'dart:io';

import 'package:flutter/material.dart';

import '../../models/upload_image.dart';

class ImageGrid extends StatelessWidget {
  const ImageGrid({
    super.key,
    required this.images,
    required this.enabled,
    required this.onRemove,
    required this.onReorder,
  });

  final List<UploadImage> images;
  final bool enabled;
  final ValueChanged<String> onRemove;
  final void Function(int oldIndex, int newIndex) onReorder;

  @override
  Widget build(BuildContext context) {
    if (images.isEmpty) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Selected images',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            Text(
              '${images.length}',
              style: theme.textTheme.labelLarge?.copyWith(
                color: theme.colorScheme.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        if (images.length > 1) ...[
          Text(
            'Drag images to change their order.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 14),
        ] else
          const SizedBox(height: 8),
        ReorderableListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          buildDefaultDragHandles: false,
          itemCount: images.length,
          onReorder: enabled ? onReorder : (_, __) {},
          proxyDecorator: (child, index, animation) {
            return AnimatedBuilder(
              animation: animation,
              child: child,
              builder: (context, child) {
                final elevation = Tween<double>(
                  begin: 0,
                  end: 8,
                ).evaluate(animation);

                return Material(
                  elevation: elevation,
                  borderRadius: BorderRadius.circular(22),
                  clipBehavior: Clip.antiAlias,
                  child: child,
                );
              },
            );
          },
          itemBuilder: (context, index) {
            final image = images[index];

            return Padding(
              key: ValueKey(image.id),
              padding: EdgeInsets.only(
                bottom: index == images.length - 1 ? 0 : 12,
              ),
              child: _ImageCard(
                image: image,
                index: index,
                enabled: enabled,
                onRemove: () => onRemove(image.id),
              ),
            );
          },
        ),
      ],
    );
  }
}

class _ImageCard extends StatelessWidget {
  const _ImageCard({
    required this.image,
    required this.index,
    required this.enabled,
    required this.onRemove,
  });

  final UploadImage image;
  final int index;
  final bool enabled;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final file = File(image.path);

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(22),
      clipBehavior: Clip.antiAlias,
      child: Container(
        height: 124,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          border: Border.all(
            color: theme.colorScheme.outlineVariant,
          ),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 124,
              height: double.infinity,
              child: Image.file(
                file,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return ColoredBox(
                    color: theme.colorScheme.surfaceContainerHighest,
                    child: Center(
                      child: Icon(
                        Icons.broken_image_outlined,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  );
                },
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 10, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Meal image ${index + 1}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Remove image',
                          onPressed: enabled ? onRemove : null,
                          icon: const Icon(Icons.close_rounded),
                        ),
                      ],
                    ),
                    const Spacer(),
                    Row(
                      children: [
                        _StatusChip(status: image.status),
                        const Spacer(),
                        ReorderableDragStartListener(
                          index: index,
                          enabled: enabled,
                          child: Padding(
                            padding: const EdgeInsets.all(8),
                            child: Icon(
                              Icons.drag_indicator_rounded,
                              color: enabled
                                  ? theme.colorScheme.onSurfaceVariant
                                  : theme.disabledColor,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.status,
  });

  final UploadStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    late final String label;
    late final IconData icon;
    late final Color backgroundColor;
    late final Color foregroundColor;

    switch (status) {
      case UploadStatus.ready:
        label = 'Ready';
        icon = Icons.check_circle_outline_rounded;
        backgroundColor = theme.colorScheme.primaryContainer;
        foregroundColor = theme.colorScheme.onPrimaryContainer;
        break;
      case UploadStatus.uploading:
        label = 'Uploading';
        icon = Icons.cloud_upload_outlined;
        backgroundColor = theme.colorScheme.secondaryContainer;
        foregroundColor = theme.colorScheme.onSecondaryContainer;
        break;
      case UploadStatus.uploaded:
        label = 'Uploaded';
        icon = Icons.cloud_done_outlined;
        backgroundColor = theme.colorScheme.primaryContainer;
        foregroundColor = theme.colorScheme.onPrimaryContainer;
        break;
      case UploadStatus.failed:
        label = 'Failed';
        icon = Icons.error_outline_rounded;
        backgroundColor = theme.colorScheme.errorContainer;
        foregroundColor = theme.colorScheme.onErrorContainer;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 10,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 16,
            color: foregroundColor,
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(
              color: foregroundColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
