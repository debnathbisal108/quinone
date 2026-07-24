import 'package:flutter/material.dart';

class AppScaffold extends StatelessWidget {
  final PreferredSizeWidget? appBar;
  final Widget body;
  final Widget? floatingActionButton;
  final Widget? bottomNavigationBar;
  final Widget? drawer;
  final Color? backgroundColor;
  final bool resizeToAvoidBottomInset;
  final bool safeArea;
  final EdgeInsetsGeometry? padding;

  const AppScaffold({
    super.key,
    this.appBar,
    required this.body,
    this.floatingActionButton,
    this.bottomNavigationBar,
    this.drawer,
    this.backgroundColor,
    this.resizeToAvoidBottomInset = true,
    this.safeArea = true,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    Widget content = body;

    if (padding != null) {
      content = Padding(
        padding: padding!,
        child: content,
      );
    }

    if (safeArea) {
      content = SafeArea(
        child: content,
      );
    }

    return Scaffold(
      appBar: appBar,
      drawer: drawer,
      backgroundColor:
          backgroundColor ??
          Theme.of(context).colorScheme.surface,
      resizeToAvoidBottomInset:
          resizeToAvoidBottomInset,
      body: AnimatedSwitcher(
        duration: const Duration(
          milliseconds: 250,
        ),
        child: content,
      ),
      floatingActionButton:
          floatingActionButton,
      bottomNavigationBar:
          bottomNavigationBar,
    );
  }
}