import 'dart:math' as math;
import 'package:flutter/material.dart';

class ScoreGauge extends StatelessWidget {
  const ScoreGauge({super.key, required this.score, this.size = 154});
  final double score;
  final double size;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox.square(
      dimension: size,
      child: CustomPaint(
        painter: _GaugePainter(
          progress: (score / 100).clamp(0, 1),
          trackColor: theme.colorScheme.surfaceContainerHighest,
          progressColor: theme.colorScheme.primary,
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(score.round().toString(), style: theme.textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w800)),
              Text('Overall score', style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
          ),
        ),
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  const _GaugePainter({required this.progress, required this.trackColor, required this.progressColor});
  final double progress;
  final Color trackColor;
  final Color progressColor;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final stroke = size.width * .075;
    final track = Paint()..color = trackColor..style = PaintingStyle.stroke..strokeWidth = stroke..strokeCap = StrokeCap.round;
    final active = Paint()..color = progressColor..style = PaintingStyle.stroke..strokeWidth = stroke..strokeCap = StrokeCap.round;
    canvas.drawArc(rect.deflate(stroke / 2), -math.pi / 2, math.pi * 2, false, track);
    canvas.drawArc(rect.deflate(stroke / 2), -math.pi / 2, math.pi * 2 * progress, false, active);
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) => oldDelegate.progress != progress || oldDelegate.progressColor != progressColor || oldDelegate.trackColor != trackColor;
}
